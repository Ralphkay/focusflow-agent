# config.py (Final Corrected Version)

import os
import sys
import json
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from urllib.parse import urlparse
import ctypes
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

def resource_path(relative_path):
    """
    Determines the correct path for resources, whether running from source
    or a PyInstaller bundle.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

_app_data_root = Path(os.getenv('APPDATA'))
APP_DATA_PATH = _app_data_root / 'FocusFlow'
APP_DATA_PATH.mkdir(parents=True, exist_ok=True)
LOG_FILE = APP_DATA_PATH / "focusflow.log"

logger = logging.getLogger(__name__)

def init_logging():
    """Initializes the logging system for the application."""
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(APP_DATA_PATH))
        if not (attrs & 0x02):
            ctypes.windll.kernel32.SetFileAttributesW(str(APP_DATA_PATH), attrs | 0x02)
    except Exception as e:
        print(f"WARNING: Failed to set 'hidden' attribute on data folder {APP_DATA_PATH}: {e}")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s',
        encoding='utf-8',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    global logger
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {LOG_FILE}")

init_logging()

dotenv_path = resource_path('.env')
load_dotenv(dotenv_path=dotenv_path)
logger.info(f"Attempting to load environment variables from: {dotenv_path}")

KEY_FILE = APP_DATA_PATH / "encryption.key"
CONFIG = {}
CONFIG["CENTRAL_DASHBOARD_URL"]  = os.getenv("CENTRAL_DASHBOARD_URL")


def normalize_domains(domains):
    """
    Normalizes a list of domain strings by parsing them and extracting the netloc.
    """
    normalized = set()
    for domain in domains:
        try:
            parsed = urlparse(f"http://{domain}" if not domain.startswith(("http://", "https://")) else domain)
            netloc = parsed.netloc
            if netloc:
                normalized.add(netloc)
        except Exception as e:
            logger.warning(f"Invalid domain in productive_websites: {domain}, error: {e}")
    return list(normalized)


def init_app_config(session):
    """
    Initializes or updates the single AppConfig record in the database.
    This should only be called once at startup.
    """
    from client_models import AppConfig

    app_config = session.query(AppConfig).first()

    initial_settings = {
        "work_hours": {"start": "08:00:00", "end": "17:00:00"},
        "work_days": [0, 1, 2, 3, 4, 5, 6],
        "sync_interval": 60,
        "max_break_minutes": 60,
        "employee_id": os.getenv("FOCUSFLOW_EMPLOYEE_ID", os.getlogin().lower() + "@cbg.com.gh"),
        "db_credentials": {
            "host": os.getenv("DB_HOST"), "port": os.getenv("DB_PORT"),
            "database": os.getenv("DB_DATABASE"), "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        },
        "log_file_path": str(LOG_FILE),
        "log_level": "INFO",
        "organization_api_key": os.getenv("FOCUSFLOW_ORGANIZATION_API_KEY"),
        "permanent_client_api_key": os.getenv("PERMANENT_CLIENT_API_KEY"),
        "CENTRAL_DASHBOARD_URL": os.getenv("CENTRAL_DASHBOARD_URL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "company_email_domain": os.getenv("COMPANY_EMAIL_DOMAIN", "@cbg.com.gh"), # <-- FIX IS HERE
        "stealth_mode": os.getenv("FOCUSFLOW_STEALTH_MODE", "true").lower() == "true",
        "app_config": {
            "finacle.exe": {"category": "Productive"}, "mstsc.exe": {"category": "Productive"},
            "temenos.exe": {"category": "Productive"}, "flexcube.exe": {"category": "Productive"},
            "t24.exe": {"category": "Productive"}, "microsoftdynamics365.exe": {"category": "Productive"},
            "sapgui.exe": {"category": "Productive"}, "bloomberg.exe": {"category": "Productive"},
            "reuters.exe": {"category": "Productive"}, "metastock.exe": {"category": "Productive"},
            "tradestation.exe": {"category": "Productive"}, "loanorigination.exe": {"category": "Productive"},
            "riskmgmt.exe": {"category": "Productive"}, "frauddetection.exe": {"category": "Productive"},
            "swiftclient.exe": {"category": "Productive"}, "fincad.exe": {"category": "Productive"},
            "sas.exe": {"category": "Productive"}, "rstudio.exe": {"category": "Productive"},
            "matlab.exe": {"category": "Productive"}, "murex.exe": {"category": "Productive"},
            "calypso.exe": {"category": "Productive"}, "summit.exe": {"category": "Productive"},
            "quantum.exe": {"category": "Productive"}, "paymentshub.exe": {"category": "Productive"},
            "outlook.exe": {"category": "Productive"}, "excel.exe": {"category": "Productive"},
            "word.exe": {"category": "Productive"}, "powerpnt.exe": {"category": "Productive"},
            "onenote.exe": {"category": "Productive"}, "visio.exe": {"category": "Productive"},
            "project.exe": {"category": "Productive"}, "access.exe": {"category": "Productive"},
            "publisher.exe": {"category": "Productive"}, "teams.exe": {"category": "Productive"},
            "ms-teams.exe": {"category": "Productive"}, "zoom.exe": {"category": "Productive"},
            "slack.exe": {"category": "Productive"}, "webex.exe": {"category": "Productive"},
            "skypeforbusiness.exe": {"category": "Productive"}, "googlemeet.exe": {"category": "Productive"},
            "dingtalk.exe": {"category": "Productive"}, "wechatwork.exe": {"category": "Productive"},
            "chrome.exe": {"category": "Productive"}, "msedge.exe": {"category": "Productive"},
            "firefox.exe": {"category": "Productive"}, "ie.exe": {"category": "Productive"},
            "citrixreceiver.exe": {"category": "Productive"}, "vmwarehorizonclient.exe": {"category": "Productive"},
            "rdpclient.exe": {"category": "Productive"}, "acrobat.exe": {"category": "Productive"},
            "foxitreader.exe": {"category": "Productive"}, "nitropro.exe": {"category": "Productive"},
            "docuware.exe": {"category": "Productive"}, "sharepointworkspace.exe": {"category": "Productive"},
            "boxsync.exe": {"category": "Productive"}, "googledrivesync.exe": {"category": "Productive"},
            "dropbox.exe": {"category": "Productive"}, "esignsoftware.exe": {"category": "Productive"},
            "pycharm64.exe": {"category": "Productive"}, "code.exe": {"category": "Productive"},
            "vs_community.exe": {"category": "Productive"}, "eclipse.exe": {"category": "Productive"},
            "intellijidea.exe": {"category": "Productive"}, "sublimetext.exe": {"category": "Productive"},
            "notepad++.exe": {"category": "Productive"}, "sqldeveloper.exe": {"category": "Productive"},
            "ssms.exe": {"category": "Productive"}, "dbeaver.exe": {"category": "Productive"},
            "pgadmin4.exe": {"category": "Productive"}, "mysqlworkbench.exe": {"category": "Productive"},
            "mongocompass.exe": {"category": "Productive"}, "git-bash.exe": {"category": "Productive"},
            "tortoisegit.exe": {"category": "Productive"}, "sourcetree.exe": {"category": "Productive"},
            "jenkins.exe": {"category": "Productive"}, "docker.exe": {"category": "Productive"},
            "kubernetes.exe": {"category": "Productive"}, "ansible.exe": {"category": "Productive"},
            "terraform.exe": {"category": "Productive"}, "postman.exe": {"category": "Productive"},
            "soapui.exe": {"category": "Productive"}, "jmeter.exe": {"category": "Productive"},
            "burpsuite.exe": {"category": "Productive"}, "putty.exe": {"category": "Productive"},
            "winscp.exe": {"category": "Productive"}, "filezilla.exe": {"category": "Productive"},
            "wireshark.exe": {"category": "Productive"}, "nmap.exe": {"category": "Productive"},
            "ciscoanyconnect.exe": {"category": "Productive"}, "forticlient.exe": {"category": "Productive"},
            "virtualbox.exe": {"category": "Productive"}, "vmwareworkstation.exe": {"category": "Productive"},
            "servicenowclient.exe": {"category": "Productive"}, "jira.exe": {"category": "Productive"},
            "confluence.exe": {"category": "Productive"}, "freshservice.exe": {"category": "Productive"},
            "solarwinds.exe": {"category": "Productive"}, "nagios.exe": {"category": "Productive"},
            "genesys.exe": {"category": "Productive"}, "avaya.exe": {"category": "Productive"},
            "ciscojabber.exe": {"category": "Productive"}, "zendesk.exe": {"category": "Productive"},
            "hrsoft.exe": {"category": "Productive"}, "payrollsoftware.exe": {"category": "Productive"},
            "expensesoftware.exe": {"category": "Productive"}, "photoshop.exe": {"category": "Productive"},
            "illustrator.exe": {"category": "Productive"}, "indesign.exe": {"category": "Productive"},
            "premiere.exe": {"category": "Productive"}, "audition.exe": {"category": "Productive"},
            "canva.exe": {"category": "Productive"}, "mailchimpsync.exe": {"category": "Productive"},
            "excelviewer.exe": {"category": "Productive"}, "powerpointviewer.exe": {"category": "Productive"},
            "wordviewer.exe": {"category": "Productive"}, "onenote.exe": {"category": "Productive"},
            "drawio.exe": {"category": "Productive"}, "vlc.exe": {"category": "Neutral"},
            "calc.exe": {"category": "Neutral"}, "notepad.exe": {"category": "Neutral"},
            "paint.exe": {"category": "Neutral"}, "media player.exe": {"category": "Neutral"},
            "games.exe": {"category": "Unproductive"}, "spotify.exe": {"category": "Unproductive"},
            "netflix.exe": {"category": "Unproductive"}, "primevideo.exe": {"category": "Unproductive"},
            "explorer.exe": {"category": "Neutral"}, "applicationframehost.exe": {"category": "Neutral"},
            "dllhost.exe": {"category": "Neutral"}, "svchost.exe": {"category": "Neutral"},
            "settingsync.exe": {"category": "Neutral"}, "taskmgr.exe": {"category": "Neutral"},
            "control.exe": {"category": "Neutral"}, "printfilterpipelinesvc.exe": {"category": "Neutral"},
            "spoolsv.exe": {"category": "Neutral"}, "csrss.exe": {"category": "Neutral"},
            "fontdrvhost.exe": {"category": "Neutral"}, "dwm.exe": {"category": "Neutral"},
            "audiodg.exe": {"category": "Neutral"}, "lsass.exe": {"category": "Neutral"},
            "winlogon.exe": {"category": "Neutral"}, "igfxem.exe": {"category": "Neutral"},
            "msdtc.exe": {"category": "Neutral"}, "runtimebroker.exe": {"category": "Neutral"},
            "ctfmon.exe": {"category": "Neutral"}, "system.exe": {"category": "Neutral"},
            "services.exe": {"category": "Neutral"}, "smss.exe": {"category": "Neutral"},
            "wininit.exe": {"category": "Neutral"}, "userinit.exe": {"category": "Neutral"},
            "consent.exe": {"category": "Neutral"}, "msiexec.exe": {"category": "Neutral"},
            "wuauclt.exe": {"category": "Neutral"}, "nvdisplay.container.exe": {"category": "Neutral"},
            "amddisplaydriver.exe": {"category": "Neutral"}, "sihost.exe": {"category": "Neutral"}
        },
        "productive_websites": normalize_domains([
            "intranet.mybank.gh", "hrportal.mybank.gh", "training.mybank.gh", "compliance.mybank.gh",
            "itsupport.mybank.gh", "analytics.mybank.gh", "clientportal.mybank.gh", "vendorportal.mybank.gh",
            "boardroom.mybank.gh", "riskdashboard.mybank.gh", "paymentsgateway.mybank.gh", "bog.gov.gh",
            "gse.com.gh", "sec.gov.gh", "nic.gov.gh", "nca.org.gh", "cybersecurity.gov.gh", "ghana.gov.gh",
            "gra.gov.gh", "ssnit.org.gh", "gipc.org.gh", "gss.gov.gh", "imf.org", "worldbank.org", "bis.org",
            "fsb.org", "fatf-gafi.org", "baselcommittee.org", "myjoyonline.com", "ghanaweb.com",
            "businessghana.com", "citinewsroom.com", "graphic.com.gh", "thebftonline.com", "reuters.com",
            "bloomberg.com", "ft.com", "wsj.com", "cnbc.com", "investopedia.com", "cfr.org", "brookings.edu",
            "nber.org", "ecb.europa.eu", "federalreserve.gov", "bankofengland.co.uk", "docs.google.com",
            "drive.google.com", "sheets.google.com", "slides.google.com", "forms.google.com", "sites.google.com",
            "meet.google.com", "calendar.google.com", "mail.google.com", "outlook.office.com",
            "teams.microsoft.com",
            "sharepoint.com", "onedrive.live.com", "portal.office.com", "admin.microsoft.com", "zoom.us",
            "slack.com",
            "webex.com", "jira.com", "confluence.com", "trello.com", "miro.com", "asana.com", "monday.com",
            "clickup.com", "servicenow.com", "salesforce.com", "sap.com", "oracle.com", "zendesk.com",
            "freshdesk.com", "hubspot.com", "atlassian.net", "github.com", "gitlab.com", "bitbucket.org",
            "stackoverflow.com", "stackexchange.com", "dev.to", "medium.com", "microsoft.com/docs",
            "docs.aws.amazon.com", "cloud.google.com/docs", "developer.oracle.com", "kubernetes.io/docs",
            "docker.com/docs", "ansible.com/docs", "terraform.io/docs", "portal.azure.com",
            "console.aws.amazon.com",
            "console.cloud.google.com", "redhat.com/docs", "vmware.com/docs",
            "cisco.com/c/en/us/support/index.html",
            "fortinet.com/support", "juniper.net/documentation", "learn.microsoft.com", "dbtlabs.com/docs",
            "airflow.apache.org/docs", "linkedin.com/learning", "coursera.org", "edx.org", "udemy.com",
            "pluralsight.com", "datacamp.com", "khanacademy.org", "cfa.org", "ghana.cib.org",
            "pwc.com/gh/en/academy.html", "kpmg.com/gh/en/home/services/advisory/training-academy.html",
            "deloitte.com/gh/en/pages/careers/training.html", "accaglobal.com", "icagh.com", "garp.org",
            "gsma.com", "afdb.org", "ecowas.int", "tralac.org", "ghana.businesschamber.com",
            "ghanaimporters.com", "ghanaexp.com", "gis.gov.gh", "nrs.gov.gh", "ghana-trade.gov.gh",
            "bankerscommittee.org", "ghana.gibs.edu.gh",
            "chatgpt.com", "gemini.google.com", "grok.x.ai", "openai.com", "anthropic.com", "perplexity.ai",
            "huggingface.co", "paperswithcode.com", "arxiv.org", "kaggle.com", "towardsdatascience.com",
            "youtube.com/c/GoogleAI", "developer.nvidia.com", "blogs.microsoft.com/ai",
            "developer.apple.com/machine-learning", "aws.amazon.com/machine-learning",
            "azure.microsoft.com/en-us/solutions/ai", "research.google", "deepmind.google",
            "ai.google", "blog.google/technology/ai/", "engineering.fb.com/category/ai-ml/",
            "openai.blog", "techcrunch.com/category/artificial-intelligence/",
            "venturebeat.com/category/artificial-intelligence/", "wired.com/tag/ai/",
            "theverge.com/ai", "datasciencecentral.com", "kdnuggets.com", "mlflow.org",
            "pytorch.org", "tensorflow.org", "scikit-learn.org", "numpy.org", "pandas.pydata.org",
            "matplotlib.org", "seaborn.pydata.org", "plotly.com", "dash.plotly.com",
            "streamlit.io", "fast.ai", "elementai.com", "vectorinstitute.ai",
            "turing.ac.uk", "alan.turing.ac.uk", "cifar.ca/ai", "mila.quebec", "vic.ai",
            "malwarebytes.com", "kaspersky.com", "avast.com", "avg.com", "bitdefender.com",
            "symantec.com", "trendmicro.com", "eset.com", "sophos.com", "crowdstrike.com",
            "paloaltonetworks.com", "checkpoint.com", "fortinet.com", "cisco.com/c/en/us/products/security.html",
            "rapid7.com", "tenable.com", "qualys.com", "nessus.org", "burpsuite.com",
            "owasp.org", "snyk.io", "veracode.com", "checkmarx.com", "contrastsecurity.com",
            "portswigger.net", "learn.snyk.io", "docs.docker.com", "cloud.google.com/kubernetes-engine",
            "aws.amazon.com/eks", "azure.microsoft.com/en-us/services/kubernetes-service",
            "grafana.com", "prometheus.io", "elk-stack.readthedocs.io", "splunk.com",
            "zabbix.com", "datadoghq.com", "newrelic.com", "dynatrace.com", "appdynamics.com",
            "elastic.co", "kibana.elastic.co", "logstash.elastic.co", "beats.elastic.co",
            "jenkins.io", "travis-ci.com", "circleci.com", "gitlab.com/ci-cd", "argocd.readthedocs.io",
            "tekton.dev", "spinnaker.io", "xebialabs.com", "hcltechsw.com/products/release-automation",
            "broadcom.com/products/software/devops/release-automation", "microfocus.com/en-us/products/alm-octane",
            "selenium.dev", "cypress.io", "playwright.dev", "jmeter.apache.org", "loadrunner.com",
            "gatling.io", "k6.io", "postman.com/automated-testing/", "soapui.org",
            "swagger.io", "rest-assured.io", "karate-labs.github.io/karate/", "pact.io",
            "mulesoft.com", "apache.org/flink", "apache.org/spark", "apache.org/kafka",
            "rabbitmq.com", "confluent.io", "redpanda.com", "fivetran.com", "stitchdata.com",
            "talend.com", "informatica.com", "tableau.com", "powerbi.microsoft.com", "looker.com",
            "qlik.com", "domo.com", "sas.com/en_us/software/visual-analytics.html",
            "microstrategy.com", "cognos.com", "thoughtspot.com", "superset.apache.org",
            "metabase.com", "redash.io", "preset.io", "dremio.com", "starburst.io",
            "trino.io", "apache.org/hive", "apache.org/presto", "apache.org/druid",
            "clickhouse.com", "snowflake.com", "databricks.com", "cloudera.com", "hortonworks.com"
        ]),
        "unproductive_websites": normalize_domains([
            # Social Media
            "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com", "snapchat.com",
            "linkedin.com/feed", "pinterest.com", "reddit.com", "discord.com", "whatsapp.com", 
            "telegram.org", "viber.com", "wechat.com", "line.me", "clubhouse.com",
            
            # Entertainment & Video
            "youtube.com", "netflix.com", "primevideo.com", "hulu.com", "disneyplus.com",
            "twitch.tv", "vimeo.com", "dailymotion.com", "9gag.com", "buzzfeed.com",
            "vice.com", "cracked.com", "funnyordie.com", "collegehumor.com",
            
            # Music & Audio
            "spotify.com", "soundcloud.com", "pandora.com", "apple.com/music",
            "music.amazon.com", "deezer.com", "tidal.com", "last.fm",
            
            # Gaming
            "steam.com", "epicgames.com", "battle.net", "origin.com", "uplay.com",
            "xbox.com", "playstation.com", "nintendo.com", "twitch.tv/gaming",
            "ign.com", "gamespot.com", "kotaku.com", "polygon.com", "gameinformer.com",
            
            # Shopping (Non-Business)
            "amazon.com/gp/product", "ebay.com", "aliexpress.com", "wish.com",
            "etsy.com", "overstock.com", "wayfair.com", "target.com", "walmart.com",
            
            # News & Gossip (Non-Professional)
            "tmz.com", "enews.com", "people.com", "usmagazine.com", "entertainment.com",
            "hollywoodreporter.com", "variety.com/entertainment", "eonline.com",
            
            # Dating
            "tinder.com", "bumble.com", "match.com", "eharmony.com", "okcupid.com",
            
            # Memes & Humor
            "imgur.com", "memebase.com", "quickmeme.com", "memegenerator.net",
            "knowyourmeme.com", "cheezburger.com",
            
            # Sports (Personal Interest)
            "espn.com", "sportscenter.com", "si.com", "bleacherreport.com",
            "nfl.com", "nba.com", "mlb.com", "fifa.com",
            
            # Personal Finance (Non-Business)
            "mint.com", "personalcapital.com", "creditkarma.com", "nerdwallet.com",
            
            # Travel (Personal)
            "booking.com", "expedia.com", "tripadvisor.com", "airbnb.com",
            "kayak.com", "priceline.com", "hotels.com",
            
            # Food & Lifestyle
            "foodnetwork.com", "allrecipes.com", "tasty.co", "epicurious.com",
            "yelp.com", "zomato.com", "grubhub.com", "doordash.com", "ubereats.com"
        ])
    }

    if app_config:
        settings = app_config.settings
        settings.update({
            "CENTRAL_DASHBOARD_URL": os.getenv("CENTRAL_DASHBOARD_URL", settings.get('CENTRAL_DASHBOARD_URL')),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", settings.get('OPENAI_API_KEY')),
            "permanent_client_api_key": os.getenv("PERMANENT_CLIENT_API_KEY", settings.get('permanent_client_api_key')),
            "employee_id": os.getenv("FOCUSFLOW_EMPLOYEE_ID", settings.get('employee_id')),
            "company_email_domain": os.getenv("COMPANY_EMAIL_DOMAIN", settings.get('company_email_domain')), # <-- FIX IS HERE
            "stealth_mode": os.getenv("FOCUSFLOW_STEALTH_MODE", "true").lower() == "true"
        })
        app_config.settings = settings
        session.commit()
        logger.info("Existing AppConfig updated from environment variables and committed.")
    else:
        app_config = AppConfig(settings=initial_settings)
        session.add(app_config)
        session.commit()
        logger.info("New AppConfig created and committed to database.")

    global CONFIG
    CONFIG.clear()
    CONFIG.update(app_config.settings)

    base_url = CONFIG.get("CENTRAL_DASHBOARD_URL")
    if base_url and "10.101.181.107" in base_url:
        logger.critical(
            "CRITICAL: The central server URL in your configuration is incorrect. "
            "Correcting to known good address for this session."
        )
        CONFIG["CENTRAL_DASHBOARD_URL"] = os.getenv("CENTRAL_DASHBOARD_URL")
        logger.warning(f"Using corrected URL for sync: {CONFIG['CENTRAL_DASHBOARD_URL']}")
    logger.info("Global CONFIG variable populated from database.")


def load_config(session):
    """
    Public function to load the CONFIG dictionary from the database.
    This is called by the main thread.
    """
    from client_models import AppConfig

    app_config = session.query(AppConfig).first()
    if app_config:
        global CONFIG
        CONFIG.clear()
        CONFIG.update(app_config.settings)

        base_url = CONFIG.get("CENTRAL_DASHBOARD_URL")
        if base_url and "10.101.181.107" in base_url:
            logger.critical("CRITICAL: Incorrect central server URL found. Correcting.")
            CONFIG["CENTRAL_DASHBOARD_URL"] = os.getenv("CENTRAL_DASHBOARD_URL")
            logger.warning(f"Using corrected URL for sync: {CONFIG['CENTRAL_DASHBOARD_URL']}")

        logger.info("Global CONFIG variable reloaded from database.")

    else:
        logger.warning("No AppConfig record found in the database. Initializing.")
        init_app_config(session)

    return CONFIG


def save_config(config_data, session):
    """
    Saves the current configuration to the database.
    """
    from client_models import AppConfig

    try:
        app_config = session.query(AppConfig).first()
        if app_config:
            app_config.settings = config_data
            session.commit()
            logger.info("Configuration saved to database.")
        else:
            logger.error("Cannot save config: no AppConfig record found.")
    except Exception as e:
        session.rollback()


def handle_encryption_key():
    """
    Handles the loading or generation of the encryption key.
    """
    global CONFIG
    if KEY_FILE.exists():
        try:
            with open(KEY_FILE, "rb") as f:
                CONFIG["encryption_key"] = f.read().decode()
            Fernet(CONFIG["encryption_key"].encode())
            logger.info("Encryption key loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading or validating encryption key: {e}. Generating a new one.", exc_info=True)
            CONFIG["encryption_key"] = Fernet.generate_key().decode()
            with open(KEY_FILE, "wb") as f:
                f.write(CONFIG["encryption_key"].encode())
            logger.info("New encryption key generated and saved.")
    else:
        CONFIG["encryption_key"] = Fernet.generate_key().decode()
        with open(KEY_FILE, "wb") as f:
            f.write(CONFIG["encryption_key"].encode())
        logger.info("New encryption key generated and saved.")

    global cipher
    cipher = Fernet(CONFIG["encryption_key"].encode())