import os
import logging
import argparse
import psycopg2
import webbrowser

from configparser import ConfigParser

from utils import FOLDER_CONFIG


# Global variables
parser = argparse.ArgumentParser(description="Provision DB")
parser.add_argument(
    "--config-filename",
    dest="config_filename",
    type=str,
    help=f"Select config filename (files must be inside the folder {FOLDER_CONFIG}/)",
    default="localhost.ini",
)
parser.parse_args()
ARGS = parser.parse_args()
config = ConfigParser()
config.read(
    os.path.join(
        FOLDER_CONFIG,
        ARGS.config_filename,
    )
)
db_config = dict(config["postgres"])


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname)s]: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Establishing the connection
    with psycopg2.connect(
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    ) as conn:
        # Creating a cursor object using the cursor() method
        cursor = conn.cursor()

        # Creating table as per requirement
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {db_config["table_pre_leades"]} (
                user_id serial NOT NULL,
                first_name varchar NULL,
                last_name varchar NULL,
                email_address varchar NULL,
                phone_number varchar NULL,
                company varchar NULL,
                CONSTRAINT leads_pk PRIMARY KEY (user_id)
            );"""
        )
        logging.info("Table created successfully!")
        conn.commit()

        # Creating initial user
        cursor.execute(
            f"""INSERT INTO {db_config["table_pre_leades"]}
                       (first_name, last_name, company, email_address, phone_number)
                       VALUES ('Bill', 'Gates', 'Microsoft', 'billgates@example.com', '+1-202-555-0131');"""
        )
        logging.info("Initial lead successfuly created!")
        conn.commit()

    # Open C3 and PyCRM
    webbrowser.open("http://localhost:9021")
    webbrowser.open("http://localhost:8000")
