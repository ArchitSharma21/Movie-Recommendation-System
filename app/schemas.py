from pydantic import BaseModel


class RecommendationOut(BaseModel):
    title: str
    score: float
    explanation: str
    signals: dict[str, float | int | str]


class RecommendationResponse(BaseModel):
    query: str
    recommendations: list[RecommendationOut]
