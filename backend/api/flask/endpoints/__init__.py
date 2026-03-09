from api.flask.endpoints.teams import teams_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": teams_bp, "parent": 'teams', "route": ''},
    ]

    for blueprint in backend_blueprints:
        app.register_blueprint(
            blueprint["bp"],
            url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}",
        )
