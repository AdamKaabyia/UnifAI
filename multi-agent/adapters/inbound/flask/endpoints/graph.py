from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from pydantic.json import pydantic_encoder
import yaml

graph_bp = Blueprint("graph", __name__)

# No endpoints for now - this is for future graph-specific operations
# Examples could be:
# - /api/graph/plan.build
# - /api/graph/plan.optimize
# - /api/graph/plan.analyze