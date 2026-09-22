import webbrowser

links = {
    "kibana": "https://kibana.nbd.int.bell.ca/wireless/app/dashboards#/view/69c957a0-3916-11ed-878a-4bc870755d4e?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-7d%2Fd,to:now))",
    "hue": "https://w0569nbdb002.bell.corp.bce.ca:8889/hue/jobbrowser/#!schedules",
    "portal": "https://bell.service-now.com/sp?id=sc_cat_item&sys_id=bef43ea214213e94f91842874b1f21fb&sysparm_domain_restore=false&sysparm_stack=no",
    "fid": "https://confluence.bell.corp.bce.ca/spaces/NSONSKBase/pages/1210105406/FIDs+Tracker",
    "kanban": "https://jira.bell.corp.bce.ca/secure/RapidBoard.jspa?rapidView=26301&selectedIssue=MNOP-4596&quickFilter=64106#",
    "calendar": "https://confluence.bell.corp.bce.ca/display/NSOMANO/calendars",
    "services": "https://confluence.bell.corp.bce.ca/spaces/NIASRE/pages/1802987394/RAN+Hadoop+-+Services",
    "netlify": "https://app.netlify.com/projects/fluffy-strudel-c33bc9/overview",
    "decom": "https://confluence.bell.corp.bce.ca/spaces/NIASRE/pages/1895185648/2026-08-27-+Decommission+Telus+Huawei+4g+5g+RAN+Hadoop+Workflows",
    "dbvis": "https://confluence.bell.corp.bce.ca/spaces/NBD/pages/443220088/Network+Hadoop+Direct+Connection+Guide+JDBC+and+ODBC",
    "tracker": "https://confluence.bell.corp.bce.ca/spaces/NIASRE/pages/1802987379/RAN+Hadoop+-+Decomm+Tracker",
    "percipio": "https://cgi.percipio.com/profile/assignments/5f3ccd00-e60b-4ab9-be24-822b3e3084ab?recurrence=1",
    "psa": "https://psa-fs.ent.cgi.com/psc/fsprda/EMPLOYEE/ERP/c/NUI_FRAMEWORK.PT_LANDINGPAGE.GBL?&lp=ERP.EMPLOYEE.UC_RS_PSA_FIN_RM",
}

print("\nAvailable Links:")
for k in links:
    print("-", k)

choice = input("\nEnter keyword: ").strip().lower()

if choice in links:
    webbrowser.open(links[choice])
else:
    print("Invalid choice")
``