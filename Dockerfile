FROM python:3.12.0a6-slim-buster

WORKDIR /app

COPY ./requirements.txt .

RUN pip3 install -r requirements.txt

RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2

RUN pip install PyJWT

COPY . .

EXPOSE 5000

# CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
CMD ["python", "app.py"]