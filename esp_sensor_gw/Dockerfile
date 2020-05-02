FROM python:3

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y bluez bluez-tools libglib2.0-dev && apt-get clean
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./esp_sensor_gw.py" ]
