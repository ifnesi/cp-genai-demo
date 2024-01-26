#!/usr/bin/env python
import os
import sys
import json
import logging
import argparse

from configparser import ConfigParser
from confluent_kafka import Consumer, Producer, KafkaException
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer

from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from utils import linkedin_lookup_agent, scrape_linkedin_profile, delivery_report


# Global Variables
FOLDER_CONFIG = "config"
ENV_VAR_FILE = ".env_api_keys"
ENV_KEYS = [
    "OPENAI_API_KEY",
    "PROXYCURL_API_KEY",
    "SERPAPI_API_KEY",
]


def main(args):
    # Check for env variables
    for key in ENV_KEYS:
        if key not in os.environ:
            logging.error(f"Environment variable {key} not defined!")
            logging.warn(f"Generate the API Keys required and have them saved into the file '{ENV_VAR_FILE}:")
            print(f"cat > {ENV_VAR_FILE} <<EOF")
            print("export OPENAI_API_KEY=<openAI_Key_here>       # https://platform.openai.com/docs/quickstart/account-setup?context=python")
            print("export PROXYCURL_API_KEY=<ProxyURL_Key_here>  # https://nubela.co/proxycurl/")
            print("export SERPAPI_API_KEY=<SERP_Key_here>     # https://serpapi.com/")
            print("EOF\n")
            sys.exit(-1)

    kconfig = ConfigParser()
    kconfig.read(
        os.path.join(
            FOLDER_CONFIG,
            args.config_filename,
        )
    )

    # Configure SR client
    sr_conf = dict(kconfig["schema-registry"])
    sr_client = SchemaRegistryClient(sr_conf)

    # Configure Kafka producer
    with open(os.path.join("schemas", "clean_leads_enriched.avro"), "r") as f:
        avro_schema = json.loads(f.read())
    producer_conf = {
        "acks": 0,
        "client.id": args.client_id,
    }
    producer_conf.update(dict(kconfig["kafka"]))
    producer = Producer(producer_conf)
    avro_serializer = AvroSerializer(
        sr_client,
        json.dumps(avro_schema),
    )

    # Configure Kafka consumer
    consumer_conf = {
        "group.id": args.group_id,
        "client.id": args.client_id,
        "auto.offset.reset": "earliest",
    }
    consumer_conf.update(dict(kconfig["kafka"]))
    consumer = Consumer(consumer_conf)
    avro_deserializer = AvroDeserializer(
        sr_client,
    )

    try:
        consumer.subscribe([args.topic])

        logging.info(
            f"Started consumer {consumer_conf['client.id']} ({consumer_conf['group.id']}) on topic '{args.topic}'"
        )
        while True:
            try:
                msg = consumer.poll(timeout=0.25)
                if msg is not None:
                    if msg.error():
                        raise KafkaException(msg.error())
                    else:
                        avro_event = avro_deserializer(
                            msg.value(),
                            SerializationContext(
                                msg.topic(),
                                MessageField.VALUE,
                            ),
                        )
                        logging.info(f"New message received: {json.dumps(avro_event)}")
                        information = f"{avro_event['FIRST_NAME']} {avro_event['LAST_NAME']} {avro_event['COMPANY']}"
                        logging.info(
                            f"Search for information: {information} with genAI!"
                        )
                        try:
                            # Get LinkedIn profile URL
                            linkedin_profile_url = linkedin_lookup_agent(
                                name=information,
                            )
                            logging.info(
                                f"LinkedIn profile URL: {linkedin_profile_url}"
                            )

                            linkedin_data = scrape_linkedin_profile(
                                linkedin_profile_url=linkedin_profile_url,
                            )
                            # Define tasks for chatgpt
                            summary_template = " ".join(
                                [
                                    "Given the Linkedin information {linkedin_information} about a person from I want you to create a JSON response with the following structure:",
                                    "1. Key: A short summary, Value: String formatted",
                                    "2. Key: Latest position, job title, company and a brief summary, Value: String formatted",
                                    "3. Key: Two interesting facts about them, Value: Array of strings",
                                    "4. Key: A topic that may interest them, Value: String formatted",
                                    "5. Key: Two creative Ice breakers to open a conversation with them, Value: Array of strings",
                                ]
                            )
                            # prepare prompt (chat)
                            summary_prompt_template = PromptTemplate(
                                input_variables=["linkedin_information"],
                                template=summary_template,
                            )
                            # create chatgpt instance
                            llm = ChatOpenAI(
                                temperature=1,
                                model_name="gpt-3.5-turbo-16k",
                            )
                            # LLM chain
                            chain = LLMChain(llm=llm, prompt=summary_prompt_template)
                            result = chain.run(linkedin_information=linkedin_data)
                            logging.info(result)

                        except Exception as err:
                            logging.error(f"An error occured (LLM): {err}")

                        else:
                            # Produce data to the enriched topic
                            topic = f"{msg.topic()}_enriched"
                            logging.info(f"Producing enriched lead to topic: {topic}")
                            producer.poll(0.0)
                            enriched_lead = {
                                "user_id": avro_event["USER_ID"],
                                "first_name": avro_event["FIRST_NAME"],
                                "last_name": avro_event["LAST_NAME"],
                                "company": avro_event["COMPANY"],
                                "email_address": avro_event.get("EMAIL_ADDRESS", "")
                                or "",
                                "phone_number": avro_event.get("PHONE_NUMBER", "")
                                or "",
                                "context": json.dumps(json.loads(result)),
                                "linkedin_profile_url": linkedin_profile_url,
                            }
                            producer.produce(
                                topic=topic,
                                key=str(avro_event["USER_ID"]).encode("utf-8"),
                                value=avro_serializer(
                                    enriched_lead,
                                    SerializationContext(
                                        topic,
                                        MessageField.VALUE,
                                    ),
                                ),
                                on_delivery=delivery_report,
                            )
                            producer.flush()

            except Exception as err:
                logging.error(f"An error occured (Confluent Platform): {err}")

    except KeyboardInterrupt:
        logging.warning("CTRL-C pressed by user!")

    finally:
        logging.info(
            f"Closing consumer {consumer_conf['client.id']} ({consumer_conf['group.id']})"
        )
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname)s]: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="GenAI Streaming Application")
    parser.add_argument(
        "--topic",
        help="Topic name",
        dest="topic",
        type=str,
        default="clean_leads",
    )
    parser.add_argument(
        "--config-filename",
        dest="config_filename",
        type=str,
        help=f"Select config filename for additional configuration, such as credentials (files must be inside the folder {FOLDER_CONFIG}/)",
        default="localhost.ini",
    )
    parser.add_argument(
        "--group-id",
        dest="group_id",
        type=str,
        help=f"Consumer's Group ID (default is 'demo-genai')",
        default="demo-genai",
    )
    parser.add_argument(
        "--client-id",
        dest="client_id",
        type=str,
        help=f"Consumer's Client ID (default is 'demo-genai-01')",
        default="demo-genai-01",
    )

    main(parser.parse_args())
