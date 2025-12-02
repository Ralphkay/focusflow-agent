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
            # Banking & Financial Software
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
            
            # Microsoft Office Suite (All Versions)
            "outlook.exe": {"category": "Productive"}, "excel.exe": {"category": "Productive"},
            "winword.exe": {"category": "Productive"}, "word.exe": {"category": "Productive"},
            "powerpnt.exe": {"category": "Productive"}, "onenote.exe": {"category": "Productive"},
            "visio.exe": {"category": "Productive"}, "project.exe": {"category": "Productive"},
            "msaccess.exe": {"category": "Productive"}, "access.exe": {"category": "Productive"},
            "mspub.exe": {"category": "Productive"}, "publisher.exe": {"category": "Productive"},
            "lync.exe": {"category": "Productive"}, "winproj.exe": {"category": "Productive"},
            "groove.exe": {"category": "Productive"}, "infopath.exe": {"category": "Productive"},
            "setlang.exe": {"category": "Productive"}, "ois.exe": {"category": "Productive"},
            "msosync.exe": {"category": "Productive"}, "officeclicktorun.exe": {"category": "Productive"},
            "appvshnotify.exe": {"category": "Productive"}, "firstrun.exe": {"category": "Productive"},
            "excelcnv.exe": {"category": "Productive"}, "wordconv.exe": {"category": "Productive"},
            "msouc.exe": {"category": "Productive"}, "clview.exe": {"category": "Productive"},
            "selfcert.exe": {"category": "Productive"}, "scanpst.exe": {"category": "Productive"},
            "osppsvc.exe": {"category": "Productive"}, "offcln.exe": {"category": "Productive"},
            "msoia.exe": {"category": "Productive"}, "onenotem.exe": {"category": "Productive"},
            "orgchart.exe": {"category": "Productive"}, "ose.exe": {"category": "Productive"},
            "msohtmed.exe": {"category": "Productive"}, "graph.exe": {"category": "Productive"},
            "onedrive.exe": {"category": "Productive"}, "onedrivestandaloneentrprisesetup.exe": {"category": "Productive"},
            
            # Microsoft Power Platform & BI
            "pbidesktop.exe": {"category": "Productive"}, "powerbi.exe": {"category": "Productive"},
            "pbidesktopmgr.exe": {"category": "Productive"}, "microsoft.mashup.container.netfx45.exe": {"category": "Productive"},
            "microsoft.mashup.container.exe": {"category": "Productive"}, "powerbireportserver.exe": {"category": "Productive"},
            "pbireportserver.exe": {"category": "Productive"}, "rsreportserver.exe": {"category": "Productive"},
            "powerapps.exe": {"category": "Productive"}, "powerautomate.exe": {"category": "Productive"},
            "pad.exe": {"category": "Productive"}, "powervirtualagents.exe": {"category": "Productive"},
            "mfcplayer.exe": {"category": "Productive"},
            
            # Microsoft Teams & Communication
            "teams.exe": {"category": "Productive"}, "ms-teams.exe": {"category": "Productive"},
            "msteams.exe": {"category": "Productive"}, "teamsupdate.exe": {"category": "Productive"},
            "teamsinstaller.exe": {"category": "Productive"}, "update.exe": {"category": "Productive"},
            "skype.exe": {"category": "Productive"}, "skypeforbusiness.exe": {"category": "Productive"},
            "lync.exe": {"category": "Productive"}, "ucmapi.exe": {"category": "Productive"},
            
            # Microsoft Development & Azure Tools
            "devenv.exe": {"category": "Productive"}, "msbuild.exe": {"category": "Productive"},
            "vshub.exe": {"category": "Productive"}, "vshost.exe": {"category": "Productive"},
            "blend.exe": {"category": "Productive"}, "vstest.console.exe": {"category": "Productive"},
            "testhost.exe": {"category": "Productive"}, "datacollector.exe": {"category": "Productive"},
            "servicehub.host.clr.exe": {"category": "Productive"}, "servicehub.identityhost.exe": {"category": "Productive"},
            "servicehub.settingshost.exe": {"category": "Productive"}, "servicehub.roslyncodeanalysisservice.exe": {"category": "Productive"},
            "servicehub.threadedwaitdialog.exe": {"category": "Productive"}, "servicehub.vsdebuggerstatic.exe": {"category": "Productive"},
            "azurecli.exe": {"category": "Productive"}, "az.exe": {"category": "Productive"},
            "azurestorageexplorer.exe": {"category": "Productive"}, "storageexplorer.exe": {"category": "Productive"},
            "azuredatastudio.exe": {"category": "Productive"}, "sqltoolsservice.exe": {"category": "Productive"},
            "microsoftazuredatastudio.exe": {"category": "Productive"}, "azd.exe": {"category": "Productive"},
            "func.exe": {"category": "Productive"}, "azurite.exe": {"category": "Productive"},
            
            # Microsoft SQL Server Tools
            "ssms.exe": {"category": "Productive"}, "sqlagent.exe": {"category": "Productive"},
            "sqlservr.exe": {"category": "Productive"}, "sqlbrowser.exe": {"category": "Productive"},
            "sqlwriter.exe": {"category": "Productive"}, "dtexec.exe": {"category": "Productive"},
            "dtsrun.exe": {"category": "Productive"}, "dtutil.exe": {"category": "Productive"},
            "msmdsrv.exe": {"category": "Productive"}, "msmdlocal.exe": {"category": "Productive"},
            "reportbuilder.exe": {"category": "Productive"}, "rs.exe": {"category": "Productive"},
            "rsconfig.exe": {"category": "Productive"}, "rsmgrpolicy.exe": {"category": "Productive"},
            "sqlcmd.exe": {"category": "Productive"}, "bcp.exe": {"category": "Productive"},
            "sqlps.exe": {"category": "Productive"}, "sqllocaldb.exe": {"category": "Productive"},
            "profiler.exe": {"category": "Productive"}, "tablediff.exe": {"category": "Productive"},
            "sqldiag.exe": {"category": "Productive"}, "ssbdiagnose.exe": {"category": "Productive"},
            
            # Microsoft Edge & IE
            "msedge.exe": {"category": "Productive"}, "msedgewebview2.exe": {"category": "Productive"},
            "microsoftedge.exe": {"category": "Productive"}, "microsoftedgecp.exe": {"category": "Productive"},
            "iexplore.exe": {"category": "Productive"}, "ie.exe": {"category": "Productive"},
            
            # Microsoft Management & Admin Tools
            "mmc.exe": {"category": "Productive"}, "gpedit.msc": {"category": "Productive"},
            "eventvwr.exe": {"category": "Productive"}, "perfmon.exe": {"category": "Productive"},
            "resmon.exe": {"category": "Productive"}, "compmgmt.msc": {"category": "Productive"},
            "diskmgmt.msc": {"category": "Productive"}, "devmgmt.msc": {"category": "Productive"},
            "azman.msc": {"category": "Productive"}, "certmgr.msc": {"category": "Productive"},
            "fsmgmt.msc": {"category": "Productive"}, "lusrmgr.msc": {"category": "Productive"},
            "printmanagement.msc": {"category": "Productive"}, "services.msc": {"category": "Productive"},
            "taskschd.msc": {"category": "Productive"}, "wf.msc": {"category": "Productive"},
            "intune.exe": {"category": "Productive"}, "sccm.exe": {"category": "Productive"},
            "configmgr.exe": {"category": "Productive"}, "mecm.exe": {"category": "Productive"},
            
            # Microsoft Dynamics & CRM
            "dynamics.exe": {"category": "Productive"}, "dynamicsax.exe": {"category": "Productive"},
            "dynamicsnav.exe": {"category": "Productive"}, "dynamicsbc.exe": {"category": "Productive"},
            "ax32.exe": {"category": "Productive"}, "microsoft.dynamics.ax.exe": {"category": "Productive"},
            "fscm.exe": {"category": "Productive"}, "dynamics365.exe": {"category": "Productive"},
            
            # Microsoft SharePoint & Collaboration
            "sharepoint.exe": {"category": "Productive"}, "sharepointworkspace.exe": {"category": "Productive"},
            "spdesign.exe": {"category": "Productive"}, "stssync.exe": {"category": "Productive"},
            "stsadm.exe": {"category": "Productive"}, "groove.exe": {"category": "Productive"},
            "msoidsvc.exe": {"category": "Productive"}, "msohtmed.exe": {"category": "Productive"},
            
            # Microsoft Terminal/Remote Desktop
            "mstsc.exe": {"category": "Productive"}, "mstscax.exe": {"category": "Productive"},
            "rdcman.exe": {"category": "Productive"}, "msra.exe": {"category": "Productive"},
            "rdpclip.exe": {"category": "Productive"}, "rdpinit.exe": {"category": "Productive"},
            "rdpinput.exe": {"category": "Productive"}, "windowsterminal.exe": {"category": "Productive"},
            "wt.exe": {"category": "Productive"}, "cmd.exe": {"category": "Productive"},
            "powershell.exe": {"category": "Productive"}, "pwsh.exe": {"category": "Productive"},
            "powershell_ise.exe": {"category": "Productive"}, "windowspowershell.exe": {"category": "Productive"},
            
            # Other Communication & Collaboration
            "zoom.exe": {"category": "Productive"}, "slack.exe": {"category": "Productive"},
            "webex.exe": {"category": "Productive"}, "webexmta.exe": {"category": "Productive"},
            "ciscowebexstart.exe": {"category": "Productive"}, "atmgr.exe": {"category": "Productive"},
            "ptinst.exe": {"category": "Productive"}, "googlemeet.exe": {"category": "Productive"},
            "dingtalk.exe": {"category": "Productive"}, "wechatwork.exe": {"category": "Productive"},
            "gotomeeting.exe": {"category": "Productive"}, "g2mstart.exe": {"category": "Productive"},
            "bluejeans.exe": {"category": "Productive"}, "ringcentral.exe": {"category": "Productive"},
            "whereby.exe": {"category": "Productive"}, "jitsi.exe": {"category": "Productive"},
            "around.exe": {"category": "Productive"}, "loom.exe": {"category": "Productive"},
            
            # Web Browsers
            "chrome.exe": {"category": "Productive"}, "firefox.exe": {"category": "Productive"},
            "opera.exe": {"category": "Productive"}, "brave.exe": {"category": "Productive"},
            "vivaldi.exe": {"category": "Productive"}, "arc.exe": {"category": "Productive"},
            "safari.exe": {"category": "Productive"}, "waterfox.exe": {"category": "Productive"},
            "chromium.exe": {"category": "Productive"}, "librewolf.exe": {"category": "Productive"},
            
            # Virtual Desktop & Remote Access
            "citrixreceiver.exe": {"category": "Productive"}, "citrixworkspace.exe": {"category": "Productive"},
            "wfica32.exe": {"category": "Productive"}, "receiver.exe": {"category": "Productive"},
            "selfservice.exe": {"category": "Productive"}, "vmwarehorizonclient.exe": {"category": "Productive"},
            "vmware-view.exe": {"category": "Productive"}, "vmplayer.exe": {"category": "Productive"},
            "rdpclient.exe": {"category": "Productive"}, "anydesk.exe": {"category": "Productive"},
            "teamviewer.exe": {"category": "Productive"}, "teamviewer_service.exe": {"category": "Productive"},
            "logmein.exe": {"category": "Productive"}, "bomgar.exe": {"category": "Productive"},
            "beyondtrust.exe": {"category": "Productive"}, "splashtop.exe": {"category": "Productive"},
            "parallels.exe": {"category": "Productive"}, "prl_client_app.exe": {"category": "Productive"},
            
            # PDF & Document Tools
            "acrobat.exe": {"category": "Productive"}, "acrord32.exe": {"category": "Productive"},
            "acrobatreader.exe": {"category": "Productive"}, "foxitreader.exe": {"category": "Productive"},
            "foxitpdfeditor.exe": {"category": "Productive"}, "foxitphantom.exe": {"category": "Productive"},
            "nitropro.exe": {"category": "Productive"}, "nitropdf.exe": {"category": "Productive"},
            "pdfxedit.exe": {"category": "Productive"}, "pdfxchange.exe": {"category": "Productive"},
            "sumatra.exe": {"category": "Productive"}, "sumatrapdf.exe": {"category": "Productive"},
            "docuware.exe": {"category": "Productive"}, "nuance.exe": {"category": "Productive"},
            "abbyy.exe": {"category": "Productive"}, "abbyyfinereader.exe": {"category": "Productive"},
            "pdfsam.exe": {"category": "Productive"}, "okular.exe": {"category": "Productive"},
            "calibre.exe": {"category": "Productive"}, "signnow.exe": {"category": "Productive"},
            "docusign.exe": {"category": "Productive"}, "adobesign.exe": {"category": "Productive"},
            "hellosign.exe": {"category": "Productive"}, "pandadoc.exe": {"category": "Productive"},
            
            # Cloud Storage & Sync
            "boxsync.exe": {"category": "Productive"}, "box.exe": {"category": "Productive"},
            "googledrivesync.exe": {"category": "Productive"}, "googledrivefs.exe": {"category": "Productive"},
            "googledrive.exe": {"category": "Productive"}, "backup and sync.exe": {"category": "Productive"},
            "dropbox.exe": {"category": "Productive"}, "icloud.exe": {"category": "Productive"},
            "icloudservices.exe": {"category": "Productive"}, "icloudphotos.exe": {"category": "Productive"},
            "megasync.exe": {"category": "Productive"}, "pcloud.exe": {"category": "Productive"},
            "syncthing.exe": {"category": "Productive"}, "nextcloud.exe": {"category": "Productive"},
            "owncloud.exe": {"category": "Productive"}, "tresorit.exe": {"category": "Productive"},
            "sharefile.exe": {"category": "Productive"}, "citrixfiles.exe": {"category": "Productive"},
            "esignsoftware.exe": {"category": "Productive"},
            
            # Development IDEs & Editors
            "pycharm64.exe": {"category": "Productive"}, "pycharm.exe": {"category": "Productive"},
            "code.exe": {"category": "Productive"}, "vscode.exe": {"category": "Productive"},
            "code - insiders.exe": {"category": "Productive"}, "vscodium.exe": {"category": "Productive"},
            "vs_community.exe": {"category": "Productive"}, "vs_professional.exe": {"category": "Productive"},
            "vs_enterprise.exe": {"category": "Productive"}, "visualstudio.exe": {"category": "Productive"},
            "eclipse.exe": {"category": "Productive"}, "eclipsec.exe": {"category": "Productive"},
            "idea64.exe": {"category": "Productive"}, "idea.exe": {"category": "Productive"},
            "intellijidea.exe": {"category": "Productive"}, "webstorm64.exe": {"category": "Productive"},
            "webstorm.exe": {"category": "Productive"}, "phpstorm64.exe": {"category": "Productive"},
            "phpstorm.exe": {"category": "Productive"}, "rubymine64.exe": {"category": "Productive"},
            "rubymine.exe": {"category": "Productive"}, "goland64.exe": {"category": "Productive"},
            "goland.exe": {"category": "Productive"}, "rider64.exe": {"category": "Productive"},
            "rider.exe": {"category": "Productive"}, "clion64.exe": {"category": "Productive"},
            "clion.exe": {"category": "Productive"}, "datagrip64.exe": {"category": "Productive"},
            "datagrip.exe": {"category": "Productive"}, "dataspell64.exe": {"category": "Productive"},
            "dataspell.exe": {"category": "Productive"}, "androidstudio64.exe": {"category": "Productive"},
            "androidstudio.exe": {"category": "Productive"}, "studio64.exe": {"category": "Productive"},
            "studio.exe": {"category": "Productive"}, "sublimetext.exe": {"category": "Productive"},
            "sublime_text.exe": {"category": "Productive"}, "subl.exe": {"category": "Productive"},
            "notepad++.exe": {"category": "Productive"}, "atom.exe": {"category": "Productive"},
            "brackets.exe": {"category": "Productive"}, "vim.exe": {"category": "Productive"},
            "gvim.exe": {"category": "Productive"}, "nvim.exe": {"category": "Productive"},
            "emacs.exe": {"category": "Productive"}, "runemacs.exe": {"category": "Productive"},
            "nano.exe": {"category": "Productive"}, "neovide.exe": {"category": "Productive"},
            "textmate.exe": {"category": "Productive"}, "bbedit.exe": {"category": "Productive"},
            "ultraedit.exe": {"category": "Productive"}, "uedit64.exe": {"category": "Productive"},
            "kate.exe": {"category": "Productive"}, "gedit.exe": {"category": "Productive"},
            "notepadqq.exe": {"category": "Productive"}, "cudatext.exe": {"category": "Productive"},
            "bluefish.exe": {"category": "Productive"}, "geany.exe": {"category": "Productive"},
            "komodo.exe": {"category": "Productive"}, "aptana.exe": {"category": "Productive"},
            "netbeans64.exe": {"category": "Productive"}, "netbeans.exe": {"category": "Productive"},
            "xcode.exe": {"category": "Productive"}, "lazarus.exe": {"category": "Productive"},
            "codeblocks.exe": {"category": "Productive"}, "qt creator.exe": {"category": "Productive"},
            "qtcreator.exe": {"category": "Productive"}, "thonny.exe": {"category": "Productive"},
            "spyder.exe": {"category": "Productive"}, "jupyter.exe": {"category": "Productive"},
            "jupyterlab.exe": {"category": "Productive"}, "jupyter-notebook.exe": {"category": "Productive"},
            "rstudio.exe": {"category": "Productive"}, "rstudio-desktop.exe": {"category": "Productive"},
            "zed.exe": {"category": "Productive"}, "lapce.exe": {"category": "Productive"},
            "helix.exe": {"category": "Productive"}, "fleet.exe": {"category": "Productive"},
            "nova.exe": {"category": "Productive"}, "cursor.exe": {"category": "Productive"},
            "windsurf.exe": {"category": "Productive"}, "codium.exe": {"category": "Productive"},
            
            # Database Tools
            "sqldeveloper.exe": {"category": "Productive"}, "sqldeveloper64.exe": {"category": "Productive"},
            "dbeaver.exe": {"category": "Productive"}, "dbeaverultimate.exe": {"category": "Productive"},
            "pgadmin4.exe": {"category": "Productive"}, "pgadmin3.exe": {"category": "Productive"},
            "mysqlworkbench.exe": {"category": "Productive"}, "mysql.exe": {"category": "Productive"},
            "mongocompass.exe": {"category": "Productive"}, "mongod.exe": {"category": "Productive"},
            "mongo.exe": {"category": "Productive"}, "mongosh.exe": {"category": "Productive"},
            "robo3t.exe": {"category": "Productive"}, "studio3t.exe": {"category": "Productive"},
            "nosqlbooster.exe": {"category": "Productive"}, "tableplus.exe": {"category": "Productive"},
            "sequel pro.exe": {"category": "Productive"}, "navicat.exe": {"category": "Productive"},
            "navicatpremium.exe": {"category": "Productive"}, "toad.exe": {"category": "Productive"},
            "razorsql.exe": {"category": "Productive"}, "databasenet.exe": {"category": "Productive"},
            "heidisql.exe": {"category": "Productive"}, "sqliteadmin.exe": {"category": "Productive"},
            "sqlite.exe": {"category": "Productive"}, "dbschema.exe": {"category": "Productive"},
            "redisdesktop.exe": {"category": "Productive"}, "redis-cli.exe": {"category": "Productive"},
            "neo4j.exe": {"category": "Productive"}, "neo4j-desktop.exe": {"category": "Productive"},
            "couchbase.exe": {"category": "Productive"}, "cassandra.exe": {"category": "Productive"},
            "elasticsearch.exe": {"category": "Productive"}, "kibana.exe": {"category": "Productive"},
            "grafana.exe": {"category": "Productive"}, "influxdb.exe": {"category": "Productive"},
            "postgres.exe": {"category": "Productive"}, "postgresql.exe": {"category": "Productive"},
            "oracledb.exe": {"category": "Productive"}, "db2.exe": {"category": "Productive"},
            
            # Version Control & CI/CD
            "git.exe": {"category": "Productive"}, "git-bash.exe": {"category": "Productive"},
            "git-cmd.exe": {"category": "Productive"}, "git-gui.exe": {"category": "Productive"},
            "gitk.exe": {"category": "Productive"}, "gh.exe": {"category": "Productive"},
            "github.exe": {"category": "Productive"}, "github desktop.exe": {"category": "Productive"},
            "githubdesktop.exe": {"category": "Productive"}, "gitlab.exe": {"category": "Productive"},
            "tortoisegit.exe": {"category": "Productive"}, "tgitcache.exe": {"category": "Productive"},
            "tgitproc.exe": {"category": "Productive"}, "tortoisesvn.exe": {"category": "Productive"},
            "tortoiseproc.exe": {"category": "Productive"}, "sourcetree.exe": {"category": "Productive"},
            "gitkraken.exe": {"category": "Productive"}, "fork.exe": {"category": "Productive"},
            "lazygit.exe": {"category": "Productive"}, "tig.exe": {"category": "Productive"},
            "smartgit.exe": {"category": "Productive"}, "tower.exe": {"category": "Productive"},
            "svn.exe": {"category": "Productive"}, "hg.exe": {"category": "Productive"},
            "mercurial.exe": {"category": "Productive"}, "bazaar.exe": {"category": "Productive"},
            "jenkins.exe": {"category": "Productive"}, "jenkins-slave.exe": {"category": "Productive"},
            "bamboo.exe": {"category": "Productive"}, "teamcity.exe": {"category": "Productive"},
            "circleci.exe": {"category": "Productive"}, "travisci.exe": {"category": "Productive"},
            "gitlab-runner.exe": {"category": "Productive"}, "actions-runner.exe": {"category": "Productive"},
            
            # DevOps & Container Tools
            "docker.exe": {"category": "Productive"}, "dockerd.exe": {"category": "Productive"},
            "docker-compose.exe": {"category": "Productive"}, "docker desktop.exe": {"category": "Productive"},
            "com.docker.cli.exe": {"category": "Productive"}, "com.docker.proxy.exe": {"category": "Productive"},
            "kubectl.exe": {"category": "Productive"}, "kubernetes.exe": {"category": "Productive"},
            "minikube.exe": {"category": "Productive"}, "kind.exe": {"category": "Productive"},
            "k9s.exe": {"category": "Productive"}, "lens.exe": {"category": "Productive"},
            "helm.exe": {"category": "Productive"}, "istioctl.exe": {"category": "Productive"},
            "oc.exe": {"category": "Productive"}, "podman.exe": {"category": "Productive"},
            "rancher.exe": {"category": "Productive"}, "rancher desktop.exe": {"category": "Productive"},
            "terraform.exe": {"category": "Productive"}, "terragrunt.exe": {"category": "Productive"},
            "ansible.exe": {"category": "Productive"}, "ansible-playbook.exe": {"category": "Productive"},
            "puppet.exe": {"category": "Productive"}, "chef.exe": {"category": "Productive"},
            "salt.exe": {"category": "Productive"}, "vagrant.exe": {"category": "Productive"},
            "packer.exe": {"category": "Productive"}, "pulumi.exe": {"category": "Productive"},
            "crossplane.exe": {"category": "Productive"}, "cdk.exe": {"category": "Productive"},
            "cdktf.exe": {"category": "Productive"}, "serverless.exe": {"category": "Productive"},
            "sam.exe": {"category": "Productive"}, "amplify.exe": {"category": "Productive"},
            "vercel.exe": {"category": "Productive"}, "netlify.exe": {"category": "Productive"},
            "flyctl.exe": {"category": "Productive"}, "railway.exe": {"category": "Productive"},
            "heroku.exe": {"category": "Productive"}, "dokku.exe": {"category": "Productive"},
            "nomad.exe": {"category": "Productive"}, "consul.exe": {"category": "Productive"},
            "vault.exe": {"category": "Productive"}, "boundary.exe": {"category": "Productive"},
            "waypoint.exe": {"category": "Productive"}, "argocd.exe": {"category": "Productive"},
            "tekton.exe": {"category": "Productive"}, "skaffold.exe": {"category": "Productive"},
            "tilt.exe": {"category": "Productive"}, "garden.exe": {"category": "Productive"},
            "okteto.exe": {"category": "Productive"}, "devspace.exe": {"category": "Productive"},
            
            # API & Testing Tools
            "postman.exe": {"category": "Productive"}, "postman agent.exe": {"category": "Productive"},
            "insomnia.exe": {"category": "Productive"}, "paw.exe": {"category": "Productive"},
            "rapidapi.exe": {"category": "Productive"}, "httpie.exe": {"category": "Productive"},
            "curl.exe": {"category": "Productive"}, "wget.exe": {"category": "Productive"},
            "soapui.exe": {"category": "Productive"}, "readyapi.exe": {"category": "Productive"},
            "jmeter.exe": {"category": "Productive"}, "apachejmeter.jar": {"category": "Productive"},
            "gatling.exe": {"category": "Productive"}, "locust.exe": {"category": "Productive"},
            "k6.exe": {"category": "Productive"}, "artillery.exe": {"category": "Productive"},
            "vegeta.exe": {"category": "Productive"}, "wrk.exe": {"category": "Productive"},
            "ab.exe": {"category": "Productive"}, "siege.exe": {"category": "Productive"},
            "selenium.exe": {"category": "Productive"}, "chromedriver.exe": {"category": "Productive"},
            "geckodriver.exe": {"category": "Productive"}, "edgedriver.exe": {"category": "Productive"},
            "cypress.exe": {"category": "Productive"}, "playwright.exe": {"category": "Productive"},
            "puppeteer.exe": {"category": "Productive"}, "testcafe.exe": {"category": "Productive"},
            "appium.exe": {"category": "Productive"}, "espresso.exe": {"category": "Productive"},
            "xcuitest.exe": {"category": "Productive"}, "detox.exe": {"category": "Productive"},
            "burpsuite.exe": {"category": "Productive"}, "burpsuitepro.exe": {"category": "Productive"},
            "zaproxy.exe": {"category": "Productive"}, "zap.exe": {"category": "Productive"},
            "owasp-zap.exe": {"category": "Productive"}, "nuclei.exe": {"category": "Productive"},
            "nikto.exe": {"category": "Productive"}, "sqlmap.exe": {"category": "Productive"},
            
            # Network & Security Tools
            "putty.exe": {"category": "Productive"}, "puttygen.exe": {"category": "Productive"},
            "pageant.exe": {"category": "Productive"}, "pscp.exe": {"category": "Productive"},
            "psftp.exe": {"category": "Productive"}, "plink.exe": {"category": "Productive"},
            "kitty.exe": {"category": "Productive"}, "mobaxterm.exe": {"category": "Productive"},
            "securecrt.exe": {"category": "Productive"}, "xshell.exe": {"category": "Productive"},
            "terminus.exe": {"category": "Productive"}, "tabby.exe": {"category": "Productive"},
            "hyper.exe": {"category": "Productive"}, "iterm.exe": {"category": "Productive"},
            "winscp.exe": {"category": "Productive"}, "filezilla.exe": {"category": "Productive"},
            "filezillaserver.exe": {"category": "Productive"}, "cyberduck.exe": {"category": "Productive"},
            "transmit.exe": {"category": "Productive"}, "fetch.exe": {"category": "Productive"},
            "forklift.exe": {"category": "Productive"}, "mountainduck.exe": {"category": "Productive"},
            "wireshark.exe": {"category": "Productive"}, "tshark.exe": {"category": "Productive"},
            "tcpdump.exe": {"category": "Productive"}, "fiddler.exe": {"category": "Productive"},
            "charles.exe": {"category": "Productive"}, "proxyman.exe": {"category": "Productive"},
            "mitmproxy.exe": {"category": "Productive"}, "nmap.exe": {"category": "Productive"},
            "zenmap.exe": {"category": "Productive"}, "masscan.exe": {"category": "Productive"},
            "ciscoanyconnect.exe": {"category": "Productive"}, "vpnclient.exe": {"category": "Productive"},
            "forticlient.exe": {"category": "Productive"}, "globalprotect.exe": {"category": "Productive"},
            "openvpn.exe": {"category": "Productive"}, "openvpn-gui.exe": {"category": "Productive"},
            "wireguard.exe": {"category": "Productive"}, "nordvpn.exe": {"category": "Productive"},
            "expressvpn.exe": {"category": "Productive"}, "surfshark.exe": {"category": "Productive"},
            "mullvad.exe": {"category": "Productive"}, "protonvpn.exe": {"category": "Productive"},
            "pfsense.exe": {"category": "Productive"}, "sophosvpn.exe": {"category": "Productive"},
            "zscaler.exe": {"category": "Productive"}, "netextender.exe": {"category": "Productive"},
            "pulse secure.exe": {"category": "Productive"}, "pulsesecure.exe": {"category": "Productive"},
            "f5vpn.exe": {"category": "Productive"}, "bigipedge.exe": {"category": "Productive"},
            "checkpointvpn.exe": {"category": "Productive"}, "trac.exe": {"category": "Productive"},
            "snx.exe": {"category": "Productive"}, "shrewsoft.exe": {"category": "Productive"},
            
            # Virtualization
            "virtualbox.exe": {"category": "Productive"}, "vboxmanage.exe": {"category": "Productive"},
            "vboxheadless.exe": {"category": "Productive"}, "vboxsds.exe": {"category": "Productive"},
            "vboxsvc.exe": {"category": "Productive"}, "vmwareworkstation.exe": {"category": "Productive"},
            "vmware.exe": {"category": "Productive"}, "vmware-vmx.exe": {"category": "Productive"},
            "vmnat.exe": {"category": "Productive"}, "vmnetcfg.exe": {"category": "Productive"},
            "vmrun.exe": {"category": "Productive"}, "hyperv.exe": {"category": "Productive"},
            "vmwp.exe": {"category": "Productive"}, "vmms.exe": {"category": "Productive"},
            "vmcompute.exe": {"category": "Productive"}, "wsl.exe": {"category": "Productive"},
            "wslhost.exe": {"category": "Productive"}, "qemu.exe": {"category": "Productive"},
            "qemu-system-x86_64.exe": {"category": "Productive"}, "utm.exe": {"category": "Productive"},
            "gnome-boxes.exe": {"category": "Productive"}, "virt-manager.exe": {"category": "Productive"},
            
            # IT Service Management
            "servicenowclient.exe": {"category": "Productive"}, "jira.exe": {"category": "Productive"},
            "confluence.exe": {"category": "Productive"}, "freshservice.exe": {"category": "Productive"},
            "freshdesk.exe": {"category": "Productive"}, "zendesk.exe": {"category": "Productive"},
            "intercom.exe": {"category": "Productive"}, "helpscout.exe": {"category": "Productive"},
            "kayako.exe": {"category": "Productive"}, "osticket.exe": {"category": "Productive"},
            "spiceworks.exe": {"category": "Productive"}, "manageengine.exe": {"category": "Productive"},
            "lansweeper.exe": {"category": "Productive"}, "pdqinventory.exe": {"category": "Productive"},
            "pdqdeploy.exe": {"category": "Productive"}, "sccm.exe": {"category": "Productive"},
            "intune.exe": {"category": "Productive"}, "jamf.exe": {"category": "Productive"},
            "kandji.exe": {"category": "Productive"}, "mosyle.exe": {"category": "Productive"},
            "addigy.exe": {"category": "Productive"}, "jumpcloud.exe": {"category": "Productive"},
            
            # Monitoring & Logging
            "solarwinds.exe": {"category": "Productive"}, "nagios.exe": {"category": "Productive"},
            "zabbix.exe": {"category": "Productive"}, "datadog.exe": {"category": "Productive"},
            "datadogagent.exe": {"category": "Productive"}, "newrelic.exe": {"category": "Productive"},
            "newrelicagent.exe": {"category": "Productive"}, "dynatrace.exe": {"category": "Productive"},
            "oneagent.exe": {"category": "Productive"}, "appdynamics.exe": {"category": "Productive"},
            "appd.exe": {"category": "Productive"}, "splunk.exe": {"category": "Productive"},
            "splunkd.exe": {"category": "Productive"}, "splunkforwarder.exe": {"category": "Productive"},
            "elastic.exe": {"category": "Productive"}, "logstash.exe": {"category": "Productive"},
            "filebeat.exe": {"category": "Productive"}, "metricbeat.exe": {"category": "Productive"},
            "packetbeat.exe": {"category": "Productive"}, "heartbeat.exe": {"category": "Productive"},
            "auditbeat.exe": {"category": "Productive"}, "functionbeat.exe": {"category": "Productive"},
            "prometheus.exe": {"category": "Productive"}, "alertmanager.exe": {"category": "Productive"},
            "node_exporter.exe": {"category": "Productive"}, "grafana-server.exe": {"category": "Productive"},
            "influxd.exe": {"category": "Productive"}, "telegraf.exe": {"category": "Productive"},
            "chronograf.exe": {"category": "Productive"}, "kapacitor.exe": {"category": "Productive"},
            "prtg.exe": {"category": "Productive"}, "cacti.exe": {"category": "Productive"},
            "mrtg.exe": {"category": "Productive"}, "icinga.exe": {"category": "Productive"},
            "checkmk.exe": {"category": "Productive"}, "observium.exe": {"category": "Productive"},
            "librenms.exe": {"category": "Productive"}, "netdata.exe": {"category": "Productive"},
            "graylog.exe": {"category": "Productive"}, "fluentd.exe": {"category": "Productive"},
            "fluentbit.exe": {"category": "Productive"}, "vector.exe": {"category": "Productive"},
            
            # Communication Center Tools
            "genesys.exe": {"category": "Productive"}, "avaya.exe": {"category": "Productive"},
            "ciscojabber.exe": {"category": "Productive"}, "ciscofinesse.exe": {"category": "Productive"},
            "five9.exe": {"category": "Productive"}, "talkdesk.exe": {"category": "Productive"},
            "aircall.exe": {"category": "Productive"}, "ringcentral.exe": {"category": "Productive"},
            "dialpad.exe": {"category": "Productive"}, "nextiva.exe": {"category": "Productive"},
            "8x8.exe": {"category": "Productive"}, "vonage.exe": {"category": "Productive"},
            "twilio.exe": {"category": "Productive"}, "bandwidth.exe": {"category": "Productive"},
            "plivo.exe": {"category": "Productive"}, "messagebird.exe": {"category": "Productive"},
            "3cx.exe": {"category": "Productive"}, "asterisk.exe": {"category": "Productive"},
            "freepbx.exe": {"category": "Productive"}, "elastix.exe": {"category": "Productive"},
            
            # HR & Business Tools
            "hrsoft.exe": {"category": "Productive"}, "payrollsoftware.exe": {"category": "Productive"},
            "expensesoftware.exe": {"category": "Productive"}, "workday.exe": {"category": "Productive"},
            "adp.exe": {"category": "Productive"}, "bamboohr.exe": {"category": "Productive"},
            "gusto.exe": {"category": "Productive"}, "paychex.exe": {"category": "Productive"},
            "namely.exe": {"category": "Productive"}, "zenefits.exe": {"category": "Productive"},
            "personio.exe": {"category": "Productive"}, "hibob.exe": {"category": "Productive"},
            "lattice.exe": {"category": "Productive"}, "culture amp.exe": {"category": "Productive"},
            "15five.exe": {"category": "Productive"}, "betterworks.exe": {"category": "Productive"},
            "greenhouse.exe": {"category": "Productive"}, "lever.exe": {"category": "Productive"},
            "icims.exe": {"category": "Productive"}, "smartrecruiters.exe": {"category": "Productive"},
            "jobvite.exe": {"category": "Productive"}, "bullhorn.exe": {"category": "Productive"},
            "concur.exe": {"category": "Productive"}, "expensify.exe": {"category": "Productive"},
            "divvy.exe": {"category": "Productive"}, "brex.exe": {"category": "Productive"},
            "ramp.exe": {"category": "Productive"}, "bill.exe": {"category": "Productive"},
            "coupa.exe": {"category": "Productive"}, "procurify.exe": {"category": "Productive"},
            
            # Creative & Design Tools
            "photoshop.exe": {"category": "Productive"}, "illustrator.exe": {"category": "Productive"},
            "indesign.exe": {"category": "Productive"}, "premiere.exe": {"category": "Productive"},
            "premierepro.exe": {"category": "Productive"}, "aftereffects.exe": {"category": "Productive"},
            "audition.exe": {"category": "Productive"}, "lightroom.exe": {"category": "Productive"},
            "lightroomclassic.exe": {"category": "Productive"}, "bridge.exe": {"category": "Productive"},
            "animate.exe": {"category": "Productive"}, "characteranimator.exe": {"category": "Productive"},
            "dimensioncc.exe": {"category": "Productive"}, "substance.exe": {"category": "Productive"},
            "xd.exe": {"category": "Productive"}, "adobexd.exe": {"category": "Productive"},
            "dreamweaver.exe": {"category": "Productive"}, "acrobatdc.exe": {"category": "Productive"},
            "creativecloudinstaller.exe": {"category": "Productive"}, "ccxprocess.exe": {"category": "Productive"},
            "cclibrary.exe": {"category": "Productive"}, "coresync.exe": {"category": "Productive"},
            "sketch.exe": {"category": "Productive"}, "figma.exe": {"category": "Productive"},
            "figmaagent.exe": {"category": "Productive"}, "invision.exe": {"category": "Productive"},
            "zeplin.exe": {"category": "Productive"}, "abstract.exe": {"category": "Productive"},
            "principle.exe": {"category": "Productive"}, "protopie.exe": {"category": "Productive"},
            "framer.exe": {"category": "Productive"}, "origami.exe": {"category": "Productive"},
            "affinity designer.exe": {"category": "Productive"}, "affinitydesigner.exe": {"category": "Productive"},
            "affinity photo.exe": {"category": "Productive"}, "affinityphoto.exe": {"category": "Productive"},
            "affinity publisher.exe": {"category": "Productive"}, "affinitypublisher.exe": {"category": "Productive"},
            "gimp.exe": {"category": "Productive"}, "gimp-2.10.exe": {"category": "Productive"},
            "inkscape.exe": {"category": "Productive"}, "krita.exe": {"category": "Productive"},
            "scribus.exe": {"category": "Productive"}, "darktable.exe": {"category": "Productive"},
            "rawtherapee.exe": {"category": "Productive"}, "digikam.exe": {"category": "Productive"},
            "corelcad.exe": {"category": "Productive"}, "coreldraw.exe": {"category": "Productive"},
            "paintshoppro.exe": {"category": "Productive"}, "canva.exe": {"category": "Productive"},
            "snagit.exe": {"category": "Productive"}, "camtasia.exe": {"category": "Productive"},
            "screenflow.exe": {"category": "Productive"}, "obs64.exe": {"category": "Productive"},
            "obs.exe": {"category": "Productive"}, "streamlabs obs.exe": {"category": "Productive"},
            "loom.exe": {"category": "Productive"}, "screencastify.exe": {"category": "Productive"},
            "cloudapp.exe": {"category": "Productive"}, "cleanshot.exe": {"category": "Productive"},
            "shottr.exe": {"category": "Productive"}, "lightshot.exe": {"category": "Productive"},
            "greenshot.exe": {"category": "Productive"}, "sharex.exe": {"category": "Productive"},
            "flameshot.exe": {"category": "Productive"}, "spectacle.exe": {"category": "Productive"},
            "blender.exe": {"category": "Productive"}, "maya.exe": {"category": "Productive"},
            "3dsmax.exe": {"category": "Productive"}, "cinema4d.exe": {"category": "Productive"},
            "houdini.exe": {"category": "Productive"}, "zbrush.exe": {"category": "Productive"},
            "sketchup.exe": {"category": "Productive"}, "autocad.exe": {"category": "Productive"},
            "acad.exe": {"category": "Productive"}, "revit.exe": {"category": "Productive"},
            "solidworks.exe": {"category": "Productive"}, "sldworks.exe": {"category": "Productive"},
            "fusion360.exe": {"category": "Productive"}, "inventor.exe": {"category": "Productive"},
            "catia.exe": {"category": "Productive"}, "creo.exe": {"category": "Productive"},
            "onshape.exe": {"category": "Productive"}, "freecad.exe": {"category": "Productive"},
            "openscad.exe": {"category": "Productive"}, "tinkercad.exe": {"category": "Productive"},
            
            # Document & Diagram Tools
            "excelviewer.exe": {"category": "Productive"}, "powerpointviewer.exe": {"category": "Productive"},
            "wordviewer.exe": {"category": "Productive"}, "drawio.exe": {"category": "Productive"},
            "draw.io.exe": {"category": "Productive"}, "lucidchart.exe": {"category": "Productive"},
            "miro.exe": {"category": "Productive"}, "whimsical.exe": {"category": "Productive"},
            "mindmeister.exe": {"category": "Productive"}, "mindnode.exe": {"category": "Productive"},
            "xmind.exe": {"category": "Productive"}, "freemind.exe": {"category": "Productive"},
            "coggle.exe": {"category": "Productive"}, "mural.exe": {"category": "Productive"},
            "figjam.exe": {"category": "Productive"}, "conceptboard.exe": {"category": "Productive"},
            "creately.exe": {"category": "Productive"}, "gliffy.exe": {"category": "Productive"},
            "cacoo.exe": {"category": "Productive"}, "processon.exe": {"category": "Productive"},
            "yed.exe": {"category": "Productive"}, "dia.exe": {"category": "Productive"},
            "omnigraffle.exe": {"category": "Productive"}, "archi.exe": {"category": "Productive"},
            "enterprisearchitect.exe": {"category": "Productive"}, "ea.exe": {"category": "Productive"},
            "staruml.exe": {"category": "Productive"}, "astah.exe": {"category": "Productive"},
            "plantuml.exe": {"category": "Productive"}, "erwin.exe": {"category": "Productive"},
            
            # Project Management & Productivity
            "trello.exe": {"category": "Productive"}, "asana.exe": {"category": "Productive"},
            "monday.exe": {"category": "Productive"}, "clickup.exe": {"category": "Productive"},
            "notion.exe": {"category": "Productive"}, "obsidian.exe": {"category": "Productive"},
            "roamresearch.exe": {"category": "Productive"}, "logseq.exe": {"category": "Productive"},
            "craft.exe": {"category": "Productive"}, "bear.exe": {"category": "Productive"},
            "ulysses.exe": {"category": "Productive"}, "iawriter.exe": {"category": "Productive"},
            "scrivener.exe": {"category": "Productive"}, "typora.exe": {"category": "Productive"},
            "marked2.exe": {"category": "Productive"}, "macdown.exe": {"category": "Productive"},
            "zettlr.exe": {"category": "Productive"}, "joplin.exe": {"category": "Productive"},
            "standardnotes.exe": {"category": "Productive"}, "simplenote.exe": {"category": "Productive"},
            "evernote.exe": {"category": "Productive"}, "onenote.exe": {"category": "Productive"},
            "notejoy.exe": {"category": "Productive"}, "coda.exe": {"category": "Productive"},
            "airtable.exe": {"category": "Productive"}, "basecamp.exe": {"category": "Productive"},
            "wrike.exe": {"category": "Productive"}, "smartsheet.exe": {"category": "Productive"},
            "teamwork.exe": {"category": "Productive"}, "podio.exe": {"category": "Productive"},
            "freedcamp.exe": {"category": "Productive"}, "redbooth.exe": {"category": "Productive"},
            "zohoproject.exe": {"category": "Productive"}, "projectlibre.exe": {"category": "Productive"},
            "omniplan.exe": {"category": "Productive"}, "ganttpro.exe": {"category": "Productive"},
            "linear.exe": {"category": "Productive"}, "height.exe": {"category": "Productive"},
            "shortcut.exe": {"category": "Productive"}, "pivotaltracker.exe": {"category": "Productive"},
            "targetprocess.exe": {"category": "Productive"}, "zenhub.exe": {"category": "Productive"},
            "todoist.exe": {"category": "Productive"}, "ticktick.exe": {"category": "Productive"},
            "things.exe": {"category": "Productive"}, "omnifocus.exe": {"category": "Productive"},
            "2do.exe": {"category": "Productive"}, "any.do.exe": {"category": "Productive"},
            "rememberthemilk.exe": {"category": "Productive"}, "habitica.exe": {"category": "Productive"},
            "toggl.exe": {"category": "Productive"}, "toggltrack.exe": {"category": "Productive"},
            "clockify.exe": {"category": "Productive"}, "harvest.exe": {"category": "Productive"},
            "rescuetime.exe": {"category": "Productive"}, "timing.exe": {"category": "Productive"},
            "timecamp.exe": {"category": "Productive"}, "everhour.exe": {"category": "Productive"},
            "hubstaff.exe": {"category": "Productive"}, "timedoctor.exe": {"category": "Productive"},
            "desktime.exe": {"category": "Productive"}, "activtrak.exe": {"category": "Productive"},
            
            # Data & Analytics Tools
            "tableau.exe": {"category": "Productive"}, "tableaudesktop.exe": {"category": "Productive"},
            "tableaureader.exe": {"category": "Productive"}, "tableaupublic.exe": {"category": "Productive"},
            "looker.exe": {"category": "Productive"}, "qlik.exe": {"category": "Productive"},
            "qlikview.exe": {"category": "Productive"}, "qliksense.exe": {"category": "Productive"},
            "domo.exe": {"category": "Productive"}, "sisense.exe": {"category": "Productive"},
            "thoughtspot.exe": {"category": "Productive"}, "metabase.exe": {"category": "Productive"},
            "superset.exe": {"category": "Productive"}, "redash.exe": {"category": "Productive"},
            "mode.exe": {"category": "Productive"}, "sigma.exe": {"category": "Productive"},
            "holistics.exe": {"category": "Productive"}, "preset.exe": {"category": "Productive"},
            "lightdash.exe": {"category": "Productive"}, "cube.exe": {"category": "Productive"},
            "hex.exe": {"category": "Productive"}, "count.exe": {"category": "Productive"},
            "observable.exe": {"category": "Productive"}, "datawrapper.exe": {"category": "Productive"},
            "flourish.exe": {"category": "Productive"}, "infogram.exe": {"category": "Productive"},
            "visme.exe": {"category": "Productive"}, "piktochart.exe": {"category": "Productive"},
            "alteryx.exe": {"category": "Productive"}, "alteryxdesigner.exe": {"category": "Productive"},
            "knime.exe": {"category": "Productive"}, "rapidminer.exe": {"category": "Productive"},
            "orangecanvas.exe": {"category": "Productive"}, "weka.exe": {"category": "Productive"},
            "spss.exe": {"category": "Productive"}, "stata.exe": {"category": "Productive"},
            "eviews.exe": {"category": "Productive"}, "minitab.exe": {"category": "Productive"},
            "jmp.exe": {"category": "Productive"}, "statistica.exe": {"category": "Productive"},
            "xlstat.exe": {"category": "Productive"}, "gretl.exe": {"category": "Productive"},
            "wolfram mathematica.exe": {"category": "Productive"}, "mathematica.exe": {"category": "Productive"},
            "maple.exe": {"category": "Productive"}, "octave.exe": {"category": "Productive"},
            "anaconda.exe": {"category": "Productive"}, "anaconda-navigator.exe": {"category": "Productive"},
            "conda.exe": {"category": "Productive"}, "python.exe": {"category": "Productive"},
            "python3.exe": {"category": "Productive"}, "pythonw.exe": {"category": "Productive"},
            "ipython.exe": {"category": "Productive"}, "pip.exe": {"category": "Productive"},
            "pip3.exe": {"category": "Productive"}, "node.exe": {"category": "Productive"},
            "npm.exe": {"category": "Productive"}, "yarn.exe": {"category": "Productive"},
            "pnpm.exe": {"category": "Productive"}, "bun.exe": {"category": "Productive"},
            "deno.exe": {"category": "Productive"}, "ruby.exe": {"category": "Productive"},
            "gem.exe": {"category": "Productive"}, "bundler.exe": {"category": "Productive"},
            "rails.exe": {"category": "Productive"}, "php.exe": {"category": "Productive"},
            "composer.exe": {"category": "Productive"}, "laravel.exe": {"category": "Productive"},
            "java.exe": {"category": "Productive"}, "javaw.exe": {"category": "Productive"},
            "javac.exe": {"category": "Productive"}, "javaws.exe": {"category": "Productive"},
            "mvn.exe": {"category": "Productive"}, "maven.exe": {"category": "Productive"},
            "gradle.exe": {"category": "Productive"}, "gradlew.exe": {"category": "Productive"},
            "ant.exe": {"category": "Productive"}, "go.exe": {"category": "Productive"},
            "rustc.exe": {"category": "Productive"}, "cargo.exe": {"category": "Productive"},
            "dotnet.exe": {"category": "Productive"}, "csc.exe": {"category": "Productive"},
            "mcs.exe": {"category": "Productive"}, "mono.exe": {"category": "Productive"},
            "nuget.exe": {"category": "Productive"}, "swift.exe": {"category": "Productive"},
            "swiftc.exe": {"category": "Productive"}, "kotlin.exe": {"category": "Productive"},
            "kotlinc.exe": {"category": "Productive"}, "scala.exe": {"category": "Productive"},
            "sbt.exe": {"category": "Productive"}, "clojure.exe": {"category": "Productive"},
            "lein.exe": {"category": "Productive"}, "erlang.exe": {"category": "Productive"},
            "erl.exe": {"category": "Productive"}, "elixir.exe": {"category": "Productive"},
            "mix.exe": {"category": "Productive"}, "haskell.exe": {"category": "Productive"},
            "ghc.exe": {"category": "Productive"}, "ghci.exe": {"category": "Productive"},
            "cabal.exe": {"category": "Productive"}, "stack.exe": {"category": "Productive"},
            "ocaml.exe": {"category": "Productive"}, "opam.exe": {"category": "Productive"},
            "julia.exe": {"category": "Productive"}, "nim.exe": {"category": "Productive"},
            "zig.exe": {"category": "Productive"}, "vlang.exe": {"category": "Productive"},
            "crystal.exe": {"category": "Productive"}, "dart.exe": {"category": "Productive"},
            "flutter.exe": {"category": "Productive"}, "lua.exe": {"category": "Productive"},
            "luajit.exe": {"category": "Productive"}, "perl.exe": {"category": "Productive"},
            "perl6.exe": {"category": "Productive"}, "raku.exe": {"category": "Productive"},
            "r.exe": {"category": "Productive"}, "rscript.exe": {"category": "Productive"},
            "rgui.exe": {"category": "Productive"}, "tcl.exe": {"category": "Productive"},
            "tclsh.exe": {"category": "Productive"}, "wish.exe": {"category": "Productive"},
            
            # Neutral Apps - System & Utilities
            "vlc.exe": {"category": "Neutral"},
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