FROM python:3.6-alpine

EXPOSE 5000

WORKDIR /app

ADD files.tar.gz /app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "run.py"]