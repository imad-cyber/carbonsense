from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.api.v1.router import api_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered CSRD/ESG Carbon Intelligence Platform. "
            "Tracks Scope 1, 2, and 3 greenhouse gas emissions "
            "for CSRD compliance reporting."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Attach limiter to app state — SlowAPI reads it from here
    application.state.limiter = limiter

    # Rate limit exceeded → our custom 429 response
    application.add_exception_handler(
        RateLimitExceeded,
        rate_limit_exceeded_handler,
    )

    application.add_middleware(SlowAPIMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "path": str(request.url),
            },
        )

    application.include_router(api_router)

    # Prometheus /metrics lives at the root, not under /api/v1
    from app.core.metrics import metrics_router
    application.include_router(metrics_router)

    @application.on_event("startup")
    async def startup_event():
        # Start the Kafka consumer in a background daemon thread.
        # If Kafka isn't running the consumer logs a warning and exits —
        # the app works fine without it (graceful degradation).
        import threading
        from app.data_pipeline.kafka_consumer import emission_consumer

        if settings.KAFKA_BOOTSTRAP_SERVERS:
            thread = threading.Thread(
                target=emission_consumer.start,
                daemon=True,
                name="kafka-consumer",
            )
            thread.start()

    @application.on_event("shutdown")
    async def shutdown_event():
        from app.data_pipeline.kafka_consumer import emission_consumer
        from app.data_pipeline.kafka_producer import emission_producer

        emission_consumer.stop()
        emission_producer.close()

    @application.get("/", tags=["Health"])
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
        }

    @application.get("/health", tags=["Health"])
    async def health():
        from app.core.cache import cache
        return {
            "status": "healthy",
            "redis": "connected" if cache.ping() else "unavailable",
        }

    return application


app = create_app()