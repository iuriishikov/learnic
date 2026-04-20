import uvicorn

from learnic.bootstrap import setup_configs
from learnic.web import create_app_production


def main() -> None:
    configs = setup_configs()
    app = create_app_production(configs)
    uvicorn.run(app, host=configs.asgi.host, port=configs.asgi.port)


if __name__ == "__main__":
    main()
