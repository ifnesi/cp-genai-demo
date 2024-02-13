import os
import psycopg2

from configparser import ConfigParser
from flask import Flask, render_template, redirect, request

from utils import FOLDER_CONFIG


####################
# Global variables #
####################
SCRIPT = os.path.splitext(os.path.basename(__file__))[0]

config = ConfigParser()
config.read(
    os.path.join(
        FOLDER_CONFIG,
        "localhost.ini",
    )
)
db_config = dict(config["postgres"])

# Webapp (Flask)
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)
app.config["SECRET_KEY"] = "46764225-ec37-4039-9591-1921b2dc20ab"


#################
# Flask routing #
#################
@app.route("/health-check", methods=["GET"])
def health_check():
    return "Ok"

@app.route("/", methods=["GET"])
def root():
    with psycopg2.connect(
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""SELECT
                user_id,
                company,
                first_name,
                last_name,
                email_address,
                phone_number
            FROM {db_config["table_pre_leades"]};"""
        )
        return render_template(
            "main.html",
            title="Py CRM",
            users=list(cursor.fetchall()),
        )

@app.route("/del-lead/<user_id>", methods=["GET"])
def del_lead(user_id: str):
    with psycopg2.connect(
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""DELETE
            FROM {db_config["table_pre_leades"]}
            WHERE user_id={user_id};"""
        )
        return redirect("/")

@app.route("/manage-lead", methods=["POST"])
def add_lead():
    with psycopg2.connect(
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    ) as conn:
        company = request.form.get("company")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        user_id = request.form.get("user_id")
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                f"""UPDATE {db_config["table_pre_leades"]} SET
                        first_name='{first_name}',
                        last_name='{last_name}',
                        company='{company}',
                        email_address='{email}',
                        phone_number='{phone_number}'
                    WHERE user_id={user_id};"""
            )
        else:
            cursor.execute(
                f"""INSERT INTO {db_config["table_pre_leades"]}
                        (first_name, last_name, company, email_address, phone_number)
                        VALUES ('{first_name}', '{last_name}', '{company}', '{email}', '{phone_number}');"""
            )
        conn.commit()
        return redirect("/")


########
# Main #
########
def main(*args):
    # If started using gunicorn
    return app

if __name__ == "__main__":
    # Start web app
    app.run(
        host="localhost",
        port=8000,
        debug=True,
    )
