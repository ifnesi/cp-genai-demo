import os
import logging
import requests

from langchain_community.utilities import SerpAPIWrapper
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


def delivery_report(err, msg):
    if err is not None:
        logging.error(f"<Callback> Delivery failed for Data record {msg.key()}: {err}")
    else:
        logging.info(
            f"<Callback> Message successfully produced to Topic '{msg.topic()}': Key = {None if msg.key() is None else msg.key().decode()}, Partition = {msg.partition()}, Offset = {msg.offset()}"
        )


# Function will search the fullname in linkedin and come back we a linkedin username profile URL
def linkedin_lookup_agent(name: str) -> str:
    # instance of ChatOpenAI
    llm = ChatOpenAI(
        temperature=0,
        model_name="gpt-3.5-turbo",
    )

    # Input person, output URL (Output Indicator)
    template = """Given the name '{name}' get the link to their Linkedin profile. Your answer should only contain the URL"""

    # Name of the Tool, Function (this will be called by the Agent if this tool will used), description is the key for choose the right cool, please be clear
    tools_for_agent1 = [
        Tool(
            name="Crawl Google 4 linkedin profile page",
            func=get_profile_url,
            description="useful for when you need get the Linkedin Page URL",
        ),
    ]

    # create template with input
    prompt_template = PromptTemplate(
        input_variables=["name"],
        template=template,
    )

    # Initialize the AGENT, verbose=TRUE means we will see everything in the reason process
    agent = initialize_agent(
        tools_for_agent1,
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )

    # run the Agent
    linkedin_username = agent.run(prompt_template.format_prompt(name=name))

    return linkedin_username


class CustomSerpAPIWrapper(SerpAPIWrapper):
    def __init__(self):
        super(CustomSerpAPIWrapper, self).__init__()

    @staticmethod
    def _process_response(res: dict) -> str:
        """Process response from SerpAPI."""
        if "error" in res.keys():
            raise ValueError(f"Got error from SerpAPI: {res['error']}")
        if "answer_box" in res.keys() and "answer" in res["answer_box"].keys():
            toret = res["answer_box"]["answer"]
        elif "answer_box" in res.keys() and "snippet" in res["answer_box"].keys():
            toret = res["answer_box"]["snippet"]
        elif (
            "answer_box" in res.keys()
            and "snippet_highlighted_words" in res["answer_box"].keys()
        ):
            toret = res["answer_box"]["snippet_highlighted_words"][0]
        elif (
            "sports_results" in res.keys()
            and "game_spotlight" in res["sports_results"].keys()
        ):
            toret = res["sports_results"]["game_spotlight"]
        elif (
            "knowledge_graph" in res.keys()
            and "description" in res["knowledge_graph"].keys()
        ):
            toret = res["knowledge_graph"]["description"]
        elif "snippet" in res["organic_results"][0].keys():
            toret = res["organic_results"][0]["link"]

        else:
            toret = "No good search result found"
        return toret


# our custom tool
def get_profile_url(name: str):
    """Searches for Linkedin Profile Page."""
    search = CustomSerpAPIWrapper()
    res = search.run(f"{name}")
    return res


def scrape_linkedin_profile(linkedin_profile_url: str):
    """
    scrape information from LinkedIn profiles,
    Manually scrape the information from the LinkedIn profile
    """

    api_endpoint = "https://nubela.co/proxycurl/api/v2/linkedin"
    header_dic = {
        "Authorization": f'Bearer {os.environ.get("PROXYCURL_API_KEY")}',
    }

    response = requests.get(
        api_endpoint,
        params={
            "url": linkedin_profile_url,
        },
        headers=header_dic,
    )

    data = response.json()
    data = {
        k: v
        for k, v in data.items()
        if v not in ([], "", "", None)
        and k not in ["people_also_viewed", "certifications"]
    }
    if data.get("groups"):
        for group_dict in data.get("groups"):
            group_dict.pop("profile_pic_url")

    return data
