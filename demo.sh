#!/bin/bash

## Functions
function usage() {
  echo "usage: ./demo.sh [-h, --help] [-x, --start] [-p, --stop]"
  echo ""
  echo "Confluent and GenAI Demo"
  echo ""
  echo "Options:"
  echo " -h, --help    Show this help message and exit"
  echo " -x, --start   Start demo"
  echo " -p, --stop    Stop demo"
  echo ""
}

function logging() {
  TIMESTAMP=`date "+%Y-%m-%d %H:%M:%S.000"`
  LEVEL=${2-"INFO"}
  if [[ $3 == "-n" ]]; then
    echo -n "$TIMESTAMP [$LEVEL]: $1"
  else
    echo "$TIMESTAMP [$LEVEL]: $1"
  fi
}

## Main
source .env
if [[ "$1" == "--stop" || "$1" == "-p" ]]; then
  # Stop demo
  logging "Stopping docker compose"
  if docker compose down ; then
    kill -9 $(ps aux | grep 'pycrm:app' | awk '{print $2}') >/dev/null 2>&1
    logging "Demo successfully stopped"
    exit 0
  else
    logging "Please start Docker Desktop!" "ERROR"
    exit -1
  fi
elif [[ "$1" == "--help" || "$1" == "-h" ]]; then
  # Demo help
  usage
  exit 0
elif [[ "$1" != "--start" && "$1" != "-x" ]]; then
  logging "Invalid argument '$1'" "ERROR"
  usage
  exit -1
fi

# Start demo
logging "Activating virtual environment"
source .venv/bin/activate

logging "Setting environment variables"
if [ ! -f $ENV_VAR_FILE ]; then
    logging "File '$ENV_VAR_FILE' not found!" "ERROR"
    echo ""
    echo "Generate the API Keys required and have them saved into the file '$ENV_VAR_FILE':"
    echo "cat > $ENV_VAR_FILE <<EOF"
    echo "export OPENAI_API_KEY=<openAI_Key_here>       # https://platform.openai.com/docs/quickstart/account-setup?context=python"
    echo "export PROXYCURL_API_KEY=<ProxyURL_Key_here>  # https://nubela.co/proxycurl/"
    echo "export SERPAPI_API_KEY=<SERP_Key_here>        # https://serpapi.com/"
    echo "EOF"
    echo ""
    exit -1
fi
source $ENV_VAR_FILE

logging "Starting docker compose"
if ! docker compose up -d --build ; then
    logging "Please start Docker Desktop!" "ERROR"
    exit -1
fi

# Waiting services to be ready
logging "Waiting Schema Registry to be ready" "INFO" -n
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$HOST:8081)" != "200" ]]
do
    echo -n "."
    sleep 1
done

echo ""
logging "Waiting Connect Cluster to be ready" "INFO" -n
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$HOST:8083)" != "200" ]]
do
    echo -n "."
    sleep 1
done

echo ""
logging "Waiting ksqlDB Cluster to be ready" "INFO" -n
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$HOST:8088/info)" != "200" ]]
do
    echo -n "."
    sleep 1
done

echo ""
logging "Waiting Confluent Control Center to be ready" "INFO" -n
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$HOST:9021)" != "200" ]]
do
    echo -n "."
    sleep 1
done

# Create PostgreSQL CDC Source connector
echo ""
logging "Creating PostgreSQL CDC Source connector ($CONNECTOR_NAME)"
curl -i -X PUT http://$HOST:8083/connectors/$CONNECTOR_NAME/config \
     -H "Content-Type: application/json" \
     -d '{
            "name": "'$CONNECTOR_NAME'",
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": "postgres",
            "database.port": "5432",
            "database.user": "'$DB_USERNAME'",
            "database.password": "'$DB_PASSWORD'",
            "database.server.name": "DockerServer",
            "database.dbname": "'$DB_NAME'",
            "table.include.list": "'$DB_SCHEMA'.'$DB_TABLE'",
            "topic.prefix": "'$DB_NAME'",
            "plugin.name": "pgoutput",
            "tasks.max": "1"
          }'
sleep 2

# Check connector status
echo ""
logging "Status PostgreSQL CDC Source connector ($CONNECTOR_NAME)"
curl -s http://$HOST:8083/connectors/$CONNECTOR_NAME/status | jq .
sleep 2

echo ""
logging "Demo environment is ready!"

# Start PyCRM web app
python3 .venv/bin/gunicorn --bind 127.0.0.1:8000 pycrm:app -w 1  --log-level CRITICAL  >/dev/null 2>&1 &
logging "Waiting CRM Web Application to be ready" "INFO" -n
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$HOST:8000/health-check)" != "200" ]]
do
    echo -n "."
    sleep 1
done

# Create PostgreSQL Tables and insert mock data
echo ""
python3 provision_db.py --config localhost.ini

# Wait for CDC topic to be created
logging "Waiting for topic '$TOPIC_CDC' to be created" "INFO" -n
while [ "$(docker exec broker /usr/bin/kafka-topics --bootstrap-server=broker:9094 --list | grep "$DB_NAME.$DB_SCHEMA.$DB_TABLE" | wc -l)" -eq "0" ]
do
    echo -n "."
    sleep 1
done

logging "Creating ksqlDB STREAMS"
while read ksqlCmd; do
  echo ""
  echo "$ksqlCmd"
  echo ""
  response=$(curl -X POST http://$HOST:8088/ksql \
       -H "Content-Type: application/vnd.ksql.v1+json; charset=utf-8" \
       --silent \
       -d @<(cat <<EOF
{
  "ksql": "$ksqlCmd",
  "streamsProperties": {$KQLDB_QUERY_PROPERTIES}
}
EOF
))
  echo ""
  echo $response | jq .
  echo ""
  if [[ ! "$response" =~ "SUCCESS" ]]; then
		if [[ ! "$response" =~ "already exists" ]]; then
    	logging "KSQL command '$ksqlCmd' did not include 'SUCCESS' in the response.  Please troubleshoot." "ERROR"
    	exit 1
		fi
  fi
done <$KSQLDB_SQL_STATEMENTS_FILE

echo ""
logging "Starting GenAI streaming application"
python3 streaming-app-genai.py --config-filename $CONFIG_FILE --topic $TOPIC_CLEAN_LEADS
