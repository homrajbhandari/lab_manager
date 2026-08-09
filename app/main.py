from fastapi import FastAPI

app = FastAPI(
    title="Research Laboratory Management System",
    description="API for managing research laboratory projects, tasks, inventory and samples.",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Welcome to Research Laboratory Management System",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }