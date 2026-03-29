"""Эндпоинт генерации маршрута по кандидатам, погоде и типу туриста."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from schemas.itinerary_schemas import (
    CandidateInput,
    CoordinatesInput,
    ItineraryDay,
    ItineraryGenerateRequest,
    ItineraryGenerateResponse,
    ItineraryStep,
    PlaceInfoInStep,
    WeatherDayInput,
)
from services.place_search_service import (
    _query_text_from_preferences,
    get_places_fallback,
    search_places_by_embedding,
)
# 🔄 Гибридный поиск будет импортирован внутри функции
from sqlalchemy.orm import Session

router = APIRouter(prefix="/itinerary", tags=["itinerary"])

# Координаты по умолчанию для Краснодарского края (если у Place нет lat/lon)
DEFAULT_COORDS = {"lat": 45.0, "lon": 38.0}

SLOTS = ["Утро", "День", "Вечер"]
SEASON_LABELS = {"winter": "зимний", "spring": "весенний", "summer": "летний", "autumn": "осенний"}
TRAVELER_LABELS = {
    "family": "Семья с детьми",
    "elderly": "Пенсионеры",
    "digital": "Фрилансер с ноутбуком",
    "gastro": "Гастроэнтузиаст",
    "active": "Активный отдых",
    "eco": "Эко/природа",
}

SEASON_BEST: dict[str, List[str]] = {
    "cl1": ["summer"],
    "cl2": ["spring", "autumn"],
    "cl3": ["spring", "summer", "autumn", "winter"],
    "cl4": ["autumn", "spring"],
    "cl5": ["spring", "summer"],
    "cl6": ["autumn", "winter"],
}

# Кластеры, которые плохо подходят для конкретного сезона
SEASON_WORST: dict[str, List[str]] = {
    "cl1": ["winter"],          # море зимой — не лучшая идея
    "cl2": ["winter"],          # природа/озеро зимой скучновато
    "cl4": ["summer", "winter"],# вино лучше весной/осенью
    "cl5": ["winter"],          # дети — лучше в тепло
    "cl6": ["spring", "summer"],# станица/ремёсла — осень/зима атмосфернее
}

# Кластеры с преимущественно outdoor-активностями (штраф при дождях)
OUTDOOR_CLUSTERS = {"cl1", "cl2", "cl5"}
# Кластеры с indoor-активностями (бонус при дождях)
INDOOR_CLUSTERS = {"cl3", "cl4", "cl6"}

KEY_HINTS: dict[str, str] = {
    "cl1": "мы поставили акцент на море рядом",
    "cl2": "добавили зелёную паузу у воды",
    "cl3": "оставили фокус на видовых остановках",
    "cl4": "встроили вкусный сценарий с дегустацией",
    "cl5": "включили семейный блок",
    "cl6": "сделали маршрут менее «толповым»",
}

def _pick_variant(options: List[str], seed: int) -> str:
    if not options:
        return ""
    return options[abs(seed) % len(options)]


def _place_to_candidate(place) -> CandidateInput:
    """Конвертирует Place (ORM) в CandidateInput."""
    rating = float(place.rating) if hasattr(place, "rating") else 0.0
    price = float(place.price) if place.price is not None else 0.0
    desc = place.description or place.description_ai or ""
    cluster_key = place.place_type or "general"
    seasons_best = SEASON_BEST.get(cluster_key, [])
    is_outdoor = cluster_key in OUTDOOR_CLUSTERS
    indoor_opts = ["помещение", "дегустации", "мастерские"] if cluster_key in INDOOR_CLUSTERS else ["кафе рядом"]
    outdoor_opts = ["прогулки", "пляж", "набережная"] if is_outdoor else ["прогулки"]

    return CandidateInput(
        # id нужен для восстановления clusterId: в генераторе мы делаем split по '-'
        id=f"{cluster_key}-p{place.place_id}",
        clusterId=cluster_key,
        title=place.name or "",
        location=place.location or "",
        coordinates=CoordinatesInput(lat=DEFAULT_COORDS["lat"], lon=DEFAULT_COORDS["lon"]),
        rating=rating,
        cost=price,
        fact=place.interesting_fact or "",
        description=desc[:500] if desc else "",
        seasonsBest=seasons_best,
        availableMonths=[],
        typeTags=[cluster_key] if cluster_key else [],
        indoorOptions=indoor_opts,
        outdoorOptions=outdoor_opts,
    )


def _month_to_season(m: int) -> str:
    if m in (12, 1, 2):
        return "winter"
    if 3 <= m <= 5:
        return "spring"
    if 6 <= m <= 8:
        return "summer"
    return "autumn"


def _cluster_key(candidate: CandidateInput) -> str:
    return candidate.id.split("-")[0] if "-" in candidate.id else ""


def _score_candidate(
    c: CandidateInput,
    traveler_type: str,
    month: int,
    rainy_days: int = 0,
) -> float:
    season = _month_to_season(month)
    key = _cluster_key(c)
    title = c.title.lower()
    location = c.location.lower()
    score = 0.0

    # --- Сезонность (главный фактор) ---
    best = SEASON_BEST.get(key)
    if best:
        if season in best:
            score += 40          # свой сезон — сильный бонус
        else:
            worst = SEASON_WORST.get(key, [])
            if season in worst:
                score -= 25      # явно не свой сезон — штраф
            # иначе нейтральный сезон: без бонуса и без штрафа

    # --- Погода (дождливые дни в поездке) ---
    if rainy_days > 0:
        if key in OUTDOOR_CLUSTERS:
            score -= rainy_days * 6   # outdoor-кластеры теряют при дождях
        if key in INDOOR_CLUSTERS:
            score += rainy_days * 5   # indoor выигрывают при дождях

    if traveler_type == "family":
        if "дет" in title:
            score += 12
        if "пар" in title:
            score += 6
        if "интересно" in location:
            score += 4
    elif traveler_type == "elderly":
        if any(w in title for w in ["мягкий", "неспеш", "тих"]):
            score += 12
        if "тих" in location:
            score += 8
    elif traveler_type == "digital":
        if any(w in title for w in ["работ", "коворкин", "вид"]):
            score += 15
        if any(w in location for w in ["кофе", "терраса"]):
            score += 6
    elif traveler_type == "gastro":
        if any(w in title for w in ["вино", "дегуст", "вкус", "ремесла"]):
            score += 15
        if any(w in location for w in ["вкус", "продукт"]):
            score += 8
    elif traveler_type == "active":
        if any(w in title for w in ["маршрут", "прогул", "троп", "паузы"]):
            score += 12
    elif traveler_type == "eco":
        if any(w in title for w in ["природ", "озер", "лес", "тропа"]):
            score += 15
        if "зел" in location:
            score += 6

    if "family" in c.typeTags and traveler_type == "family":
        score += 5
    if "elderly-friendly" in c.typeTags and traveler_type == "elderly":
        score += 5
    if "gastro" in c.typeTags and traveler_type == "gastro":
        score += 5
    if "eco" in c.typeTags and traveler_type == "eco":
        score += 5

    score += round(c.rating * 2)
    return score


def _why_for_place(c: CandidateInput, day_index: int, traveler_type: str, month: int) -> str:
    season = _month_to_season(month)
    key = _cluster_key(c)
    seed = day_index + len(c.title) + int(c.cost or 0)

    base = {
        "summer": "в тёплый сезон особенно приятно гулять без спешки",
        "winter": "в холодный сезон важны уют и «смысловые» остановки",
        "spring": "весной ощущается свежесть и легко планировать короткие маршруты",
        "autumn": "осенью выигрывают атмосфера и погода для прогулок",
    }.get(season, "под настроение")

    audience = {
        "family": "подходит семье: спокойный темп и понятные сценарии",
        "elderly": "подходит тем, кому важны тишина и удобная логика передвижений",
        "digital": "хорошо для фокуса: вид, кофе и рабочий ритм",
        "gastro": "про вкус: дегустация/ремесло и «история» вокруг места",
        "active": "даёт движение: прогулки и короткие «точки-успеха»",
        "eco": "про природу: вода/лес/тропа и ощущение «я перезагрузился(лась)»",
    }.get(traveler_type, "под настроение")

    hint = KEY_HINTS.get(key, "под настроение")
    fact_text = f"Факт: {c.fact}." if c.fact else ""
    desc_snippet = ""
    if c.description:
        first_sentence = c.description.split(".")[0].strip()
        if first_sentence:
            desc_snippet = f" {first_sentence}."

    intro = _pick_variant(
        [
            f"Выбранное место: «{c.title}».",
            f"Для дня {day_index + 1} выбрали «{c.title}».",
            f"Опорная точка дня {day_index + 1}: «{c.title}».",
        ],
        seed,
    )
    return f"{intro} {hint} — {audience}. {base}. {fact_text}{desc_snippet}".strip()


def _logistics_notes(
    c: CandidateInput,
    day_index: int,
    weather: WeatherDayInput | None,
    traveler_type: str,
    month: int,
) -> str:
    seed = day_index + len(c.title) + int(c.cost or 0)
    parts: List[str] = []
    if weather:
        if weather.isRainy:
            indoor = c.indoorOptions[:2] if c.indoorOptions else ["помещение рядом"]
            rain_variants = [
                f"При дожде ({weather.weatherLabel}, {weather.precipitationSum} мм): {', '.join(indoor)}.",
                f"Погода с осадками ({weather.weatherLabel}): делаем упор на {', '.join(indoor)}.",
                f"На случай осадков ({weather.precipitationSum} мм) планируем больше времени в формате: {', '.join(indoor)}.",
            ]
            parts.append(_pick_variant(rain_variants, seed))
        else:
            outdoor = c.outdoorOptions[:2] if c.outdoorOptions else ["прогулки"]
            dry_variants = [
                f"Погода {weather.weatherLabel}: {', '.join(outdoor)}.",
                f"Без сильных осадков — комфортно идти через {', '.join(outdoor)}.",
                f"Условия дня ({weather.weatherLabel}) подходят для формата: {', '.join(outdoor)}.",
            ]
            parts.append(_pick_variant(dry_variants, seed))

    if c.location:
        location_variants = [
            f"Район: {c.location}.",
            f"Опорная локация дня: {c.location}.",
            f"Маршрут строим вокруг точки «{c.location}».",
        ]
        parts.append(_pick_variant(location_variants, seed + 3))

    if c.cost:
        budget_variants = [
            f"Ориентир по бюджету точки: {round(c.cost)} ₽.",
            f"Планируем расходы дня с опорой на бюджет {round(c.cost)} ₽.",
            f"Бюджетная метка по месту: {round(c.cost)} ₽.",
        ]
        parts.append(_pick_variant(budget_variants, seed + 7))

    if c.suitabilityFlags and c.suitabilityFlags.accessibilityNotes:
        parts.append(c.suitabilityFlags.accessibilityNotes)
    return " ".join(parts) if parts else "Обычная логистика."


@router.post("/generate", response_model=ItineraryGenerateResponse)
def generate_itinerary(
    payload: ItineraryGenerateRequest,
    db: Session = Depends(get_db),
) -> ItineraryGenerateResponse:
    """
    Генерирует маршрут с гибридным поиском мест:
    1. DeepSeek генерирует умный поисковый запрос
    2. TF-IDF быстро ищет top-20 мест
    3. DeepSeek переранжирует результаты
    4. Система строит оптимальный маршрут
    """
    from services.hybrid_search_service import hybrid_search_places
    
    candidates = list(payload.candidates) if payload.candidates else []

    db_place_by_id: dict[str, object] = {}
    if not candidates:
        # 🔄 ГИБРИДНЫЙ ПОИСК с DeepSeek + TF-IDF
        db_places = hybrid_search_places(
            db=db,
            traveler_type=payload.travelerType or "family",
            start_date=payload.startDate,
            weather_labels=[w.weatherLabel for w in (payload.weatherByDay or []) if w.weatherLabel],
            limit=12
        )
        
        candidates = [_place_to_candidate(p) for p in db_places]
        db_place_by_id = {c.id: p for c, p in zip(candidates, db_places)}

    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="Нет мест в БД. Запустите seed: docker exec cluster_api python scripts/seed_demo_places.py",
        )

    duration = payload.durationDays or 3
    traveler_type = payload.travelerType or "family"

    # Парсим месяц из startDate (YYYY-MM-DD)
    try:
        parts = payload.startDate.split("-")
        month = int(parts[1]) if len(parts) >= 2 else 6
    except (ValueError, IndexError):
        month = 6

    weather_by_day = payload.weatherByDay or []

    rainy_days = sum(1 for w in weather_by_day if w.isRainy)

    sorted_candidates = sorted(
        candidates,
        key=lambda c: _score_candidate(c, traveler_type, month, rainy_days),
        reverse=True,
    )

    day_buckets: List[ItineraryDay] = [
        ItineraryDay(dayIndex=i, steps=[])
        for i in range(duration)
    ]

    for i, cand in enumerate(sorted_candidates):
        day_index = i % duration
        slot_idx = i % 3
        slot = SLOTS[slot_idx]
        weather = weather_by_day[day_index] if day_index < len(weather_by_day) else None

        why = _why_for_place(cand, day_index, traveler_type, month)
        logistics = _logistics_notes(cand, day_index, weather, traveler_type, month)

        place_info = None
        if cand.id in db_place_by_id:
            p = db_place_by_id[cand.id]
            imgs = getattr(p, "images", None) or []
            photo_url = imgs[0].image_url if imgs else ""
            place_info = PlaceInfoInStep(
                id=cand.id,
                title=cand.title,
                location=cand.location,
                cost=cand.cost,
                rating=cand.rating,
                fact=cand.fact,
                description=cand.description[:200] if cand.description else "",
                photoUrl=photo_url,
            )

        day_buckets[day_index].steps.append(
            ItineraryStep(
                slot=slot,
                placeId=cand.id,
                why=why,
                logisticsNotes=logistics,
                placeInfo=place_info,
            )
        )

    season = _month_to_season(month)
    season_adj = SEASON_LABELS.get(season, season)
    traveler_label = TRAVELER_LABELS.get(traveler_type, traveler_type)
    overall_why = (
        f"ИИ-куратор: для {traveler_label} в {season_adj} период мы распределили места по дням "
        "так, чтобы сохранить темп, логичность и «вау»-атмосферу."
    )

    return ItineraryGenerateResponse(
        itineraryDays=day_buckets,
        overallWhy=overall_why,
    )
