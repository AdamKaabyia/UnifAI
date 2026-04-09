from endpoints.protected_routes import protected_bp
from endpoints.health import health_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": protected_bp, "parent": 'protected', "route": ''},
        {"bp": health_bp, "parent": 'health', "route": ''},

    ]
    
    # register all other blueprints in the app
    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")
