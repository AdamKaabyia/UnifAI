FROM registry.access.redhat.com/ubi9/python-311

USER root
RUN dnf update -y && dnf install -y vim less iputils mesa-libGL && dnf clean all

USER default

# Copy tests folder contents
ADD  --chown=default:root --chmod=777 ./tests $HOME/tests

WORKDIR $HOME/tests

# Ensure scripts are executable
RUN chmod +x docs/run_stress_test.sh && chmod -R g+w .

RUN pip3 install --upgrade pip virtualenv
RUN python3 -m venv venv

# Activate venv and install requirements
RUN /bin/bash -c "source venv/bin/activate && \
    pip install -r docs/requirements_stress_test.txt"

WORKDIR $HOME/tests/docs

# =============================================================================
# NOTE: SHARED VOLUME FOR DOCS
# =============================================================================
# This container MUST have access to a shared volume where documents are uploaded.
# Mount the shared volume at runtime:
#   docker run -v /path/to/shared/docs:/app/shared ...
#
# The UPLOAD_FOLDER environment variable should point to this mounted volume.
# =============================================================================

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================
# The following ENV parameters can be declared when running this image:
#
#   API_BASE_URL    - Backend API URL (default: http://localhost:13457/api)
#   MONGODB_HOST    - MongoDB host address (default: localhost)
#   MONGODB_PORT    - MongoDB port number (default: 27017)
#   UPLOAD_FOLDER   - Path to shared volume for uploaded docs (default: /app/shared)
#
# Example:
#   docker run -e API_BASE_URL=http://backend:13457/api \
#              -e MONGODB_HOST=mongo \
#              -e MONGODB_PORT=27017 \
#              -e UPLOAD_FOLDER=/app/shared \
#              -v /host/shared/docs:/app/shared \
#              tests-image
# =============================================================================

ENTRYPOINT ["/bin/bash", "-c", "source ../venv/bin/activate && python3 verify_setup.py"]

