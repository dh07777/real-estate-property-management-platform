from flask import Blueprint, current_app, jsonify, Response

bp = Blueprint("docs", __name__, url_prefix="/api")


@bp.get("/openapi.json")
def openapi():
    """OpenAPI spec generated from the registered Flask routes."""
    paths = {}
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith("/api") or rule.endpoint == "static":
            continue
        path = rule.rule.replace("<int:", "{").replace("<path:", "{").replace("<", "{").replace(">", "}")
        for m in rule.methods - {"HEAD", "OPTIONS"}:
            fn = current_app.view_functions[rule.endpoint]
            paths.setdefault(path, {})[m.lower()] = {"summary": rule.endpoint, "description": (fn.__doc__ or "").strip(),
                                                      "responses": {"200": {"description": "OK"}}}
    return jsonify(openapi="3.0.3", info={"title": "EstateFlow API", "version": "1.0.0"}, paths=paths)


@bp.get("/docs")
def swagger():
    html = """<!doctype html><html><head><title>EstateFlow API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head><body>
<div id="ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#ui'})</script></body></html>"""
    return Response(html, mimetype="text/html")
