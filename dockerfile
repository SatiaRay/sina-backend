FROM python

RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY wait-for.py .
COPY wait-for-it.sh .
EXPOSE 8000