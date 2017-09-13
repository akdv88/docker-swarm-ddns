#!/usr/bin/env python3.6

from time import sleep
import argparse, \
       ast, \
       docker, \
       dns.resolver, \
       dns.query, \
       dns.tsigkeyring, \
       dns.update, \
       os, \
       sys

parser = argparse.ArgumentParser()
parser.add_argument("-s",help="list of ip address[es] of your swarm nodes. Format: ipaddress,..",required=True)
parser.add_argument("-n",help="your dnserver[s] configuration. Format: \"{'name':{'ip':'youripaddress','key':'yourupdatekey}}\"",required=True)
parser.add_argument("-d",help="your domain name (example.)",required=True)
args = parser.parse_args()

swnodes = args.s.split(',')
dnservers = ast.literal_eval(args.n)
domain = args.d

def docker_query():
    svc_list = {}
    try:
        conn = docker.from_env()
    except:
        print("Error: No connection to docker socket!")
# Initialization
    for service in conn.services.list():
        if 'add.dns' in service.attrs['Spec']['Labels']:
            svc = service.attrs['Spec']['Labels']['add.dns']
            svc_list[service.attrs['Spec']['Name']] = svc
            print('\nService/Action:', service.attrs['Spec']['Name']+'/add(update)')
            try:
                dns_add(svc.replace('_','-').lower())
            except:
                print("Error: DNS update failed!")
# Event Listener
    for event in conn.events('','','','true'):
        svc_id = event['Actor']['ID']
        if event['Type'] == 'service' and (event['Action'] == 'create' or event['Action'] == 'update') and 'add.dns' in conn.services.get(svc_id).attrs['Spec']['Labels']:
            svc_name = conn.services.get(svc_id).attrs['Spec']['Name']
            svc = conn.services.get(svc_id).attrs['Spec']['Labels']['add.dns']
            print('\nService/Action:', svc_name+'/'+event['Action'])
            if event['Action'] == 'create' or (event['Action'] == 'update' and svc_name not in svc_list):
                try:
                    dns_add(svc.replace('_','-').lower())
                except:
                    print("Error: DNS update failed!")
            elif event['Action'] == 'update' and svc_name in svc_list:
                svc_old = svc_list[svc_name]
                try:
                    dns_remove(svc_old.replace('_','-').lower())
                except:
                    print("Error: DNS update failed!")
                try:
                    dns_add(svc.replace('_','-').lower())
                except:
                    print("Error: DNS update failed!")
            svc_list[svc_name] = svc
        elif event['Type'] == 'service' and event['Action'] == 'remove':
            svc_name = event['Actor']['Attributes']['name']
            svc = svc_list[svc_name]
            svc_list.pop(svc_name)
            print(svc_list)
            print('\nService/Action:', svc_name+'/'+event['Action'])
            try:
                dns_remove(svc.replace('_','-').lower())
            except:
                print("Error: DNS update failed!")

def dns_add(svc):
    for host, conf in dnservers.items():
        print('Add/Update DNS Record \''+svc+'\' sent to',host,'dnserver ('+conf['ip']+')')
        keyring = dns.tsigkeyring.from_text({
                'rndc-key.' : conf['key']
                })
        update = dns.update.Update(domain, keyring=keyring)
        for swip in swnodes:
            update.add(svc, 15, 'a', swip)
            resp = dns.query.tcp(update, conf['ip'])

def dns_remove(svc):
    for host, conf in dnservers.items():
        print('Remove DNS Record \''+svc+'\' sent to',host,'dnserver ('+conf['ip']+')')
        keyring = dns.tsigkeyring.from_text({
                'rndc-key.' : conf['key']
                })
        update = dns.update.Update(domain, keyring=keyring)
        update.delete(svc, 'a')
        resp = dns.query.tcp(update, conf['ip'])

if __name__ == "__main__":
    try:
        docker_query()
    except KeyboardInterrupt:
        pass
    finally:
        print('\nScript soft exit')
