import logging
import psycopg2
import webbrowser


# Global variables
TABLE_NAME = "public.pre_leads"


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname)s]: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Establishing the connection
    with psycopg2.connect(
        database="postgres",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432",
    ) as conn:
        # Creating a cursor object using the cursor() method
        cursor = conn.cursor()

        # Creating table as per requirement
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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
            f"""INSERT INTO {TABLE_NAME}
                       (first_name, last_name, company, email_address, phone_number)
                       VALUES ('Bill', 'Gates', 'Microsoft', 'billgates@example.com', '+1-202-555-0131');"""
        )
        logging.info("Initial lead successfuly created!")
        conn.commit()

    # Open C3 and PGAdmin
    webbrowser.open("http://localhost:9021")
    webbrowser.open("http://localhost:5050")
