#!/bin/bash
export PATH=/apollo/env/brazilCLI/public-bin:/apollo/env/brazilCLI/bin:/usr/local/bin:/usr/bin:/bin:$PATH
export AWS_SHARED_CREDENTIALS_FILE=/apollo/var/env/CoverityCruxAnalyzer/credentials/307277300629/KPPv2TaskRole/credentials

# Get GitFarm SSH ticket
TICKET=$(python3 -c "
import boto3, json, urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session
import warnings
warnings.filterwarnings('ignore')
session = Session()
creds = session.get_credentials().get_frozen_credentials()
payload = json.dumps({'Service':'com.amazon.brazil.gitfarm.service#GitFarmService','Operation':'com.amazon.brazil.gitfarm.service#getTemporarySshTicketV2','Input':{}}).encode()
req = AWSRequest(method='POST',url='https://gitfarm-prod-awsauth.corp.amazon.com/',data=payload,headers={'Content-Type':'application/x-amz-json-1.1','X-Amz-Target':'GitFarmService.getTemporarySshTicketV2'})
SigV4Auth(creds,'GitFarmService','us-west-2').add_auth(req)
r = urllib.request.Request('https://gitfarm-prod-awsauth.corp.amazon.com/',data=payload,headers=dict(req.headers),method='POST')
resp = urllib.request.urlopen(r,timeout=10)
print(json.loads(resp.read())['ticket'])
")

export GITFARM_ROBOT_USER_KEY="$TICKET"
export GIT_SSH="/local/home/coverity-bot/gitfarm-ssh-wrapper.sh"

"$@"
