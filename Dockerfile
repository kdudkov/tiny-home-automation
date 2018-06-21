FROM python:3.6-alpine

EXPOSE 5000

WORKDIR /app

COPY *.py requirements.txt /app/
COPY actors/ /app/actors/
COPY core/ /app/core/
COPY config/ /app/config/
COPY static/ /app/static/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "run.py"]