#!/usr/bin/env python
# -*- encoding: UTF8 -*-

#######################################################################
#
#    Copyright (c) 2018 Stefan Helmert <stefan.helmert@t-online.de>
#
#######################################################################

import configparser

from simplelogger import simplelogger as log


def srvParseDel(srv):
    defaultAggrDel = {'content': [], 'prio': '*', 'key': []}
    for i, e in enumerate(srv['aggrDelList']):
        aggrDel = dict(defaultAggrDel)
        aggrDel.update(e)
        aggrDel['content'].extend(6 * ['*'])
        aggrDel['key'].extend(6 * ['*'])
        srv['aggrDelList'][i] = aggrDel
    log.debug(srv['aggrDelList'])
    srvAggrDel = [{'prio': e['prio'], 'service': e['key'][1], 'proto': e['key'][2], 'port': e['key'][3], 'weight': e['key'][4]} for e in srv['aggrDelList']]
    srvAggrDel = [{k: v for k, v in e.items() if '*' != str(v)} for e in srvAggrDel]
    return srvAggrDel

def srvParseAdd(srv):
    defaultAggrAdd = {'content': [], 'prio': '*', 'key': []}
    for i, e in enumerate(srv['aggrAddList']):
        aggrAdd = dict(defaultAggrAdd)
        aggrAdd.update(e)
        aggrAdd['content'].extend(6 * ['*'])
        aggrAdd['key'].extend(6 * ['*'])
        srv['aggrAddList'][i] = aggrAdd
    srvAggrAddKey = [{'server': e['content'][0], 'prio': e['prio'], 'service': e['key'][1], 'proto': e['key'][2], 'port': e['key'][3], 'weight': e['key'][4]} for e in srv['aggrAddList']]
    srvAggrAddVal = [{'server': e['content'][0], 'prio': e['prio'], 'service': e['content'][5], 'proto': e['content'][4], 'port': e['content'][3], 'weight': e['content'][2]} for e in srv['aggrAddList']]
    for i, e in enumerate(srvAggrAddVal):
        srvAggrAddKey[i].update(e)
    srvAggrAdd = [{k: v for k, v in e.items() if '*' != str(v)} for e in srvAggrAddKey]
    return srvAggrAdd

class ConfigReader:
    def __init__(self):
        self.cp = configparser.ConfigParser()
        self.filenameList = []
        self.domainconfig = {}
        self.certconfig = {}
        self.dkimconfig = {}
        self.conflictingservices = {}

    def setFilenames(self, filenames):
        if filenames is None:
            return
        if type(filenames) is str:
            filenames = [filenames]
        self.filenameList = filenames

    def addFilenames(self, filenames):
        if filenames is None:
            return
        if type(filenames) is str:
            filenames = [filenames]
        self.filenameList.extend(filenames)

    def open(self):
        self.cp = configparser.ConfigParser()
        self.cp.read(self.filenameList)

    def interprete(self):
        self.domainconfig = interpreteDomainConfig(self.cp)
        self.certconfig = interpreteCertConfig(self.cp)
        self.dkimconfig = interpreteDKIMConfig(self.cp)
        self.conflictingservices = getConflictingServices(self.certconfig)

def prioParse(content, rrType='mx', removeSpaces=True, dotsLeft=0, keySplit=False, colonArgs=False):
    setList = []
    addList = []
    aggrAddList = []
    aggrDelList = []
    for k, v in content.items():
        if '+' == k[-1]:
            addMode = True
            k = k[:-1]
        else:
            addMode = False
        ks = k.rsplit('.', dotsLeft + 1)
        if rrType != k.split('.')[0]:
            continue
        log.debug(v)
        if removeSpaces is True:
            v = v.replace(' ', '')
        vList = v.split(',')
        for v in vList:
            vs = v.split(':')
            if keySplit is True:
                ks[0] = ks[0].split('.')
            if colonArgs is True:
                args = vs
            else:
                args = vs[0]
            item = {'content': args, 'key': ks[0], 'delprio': '*', 'addprio': 10}
            baseItem = {'content': args, 'key': ks[0]}
            delItem = dict(baseItem)
            del delItem['content']
            addItem = dict(baseItem)
            addItem['prio'] = 10 # default
            if 2 == len(ks):
                item['delprio'] = ks[1]
                item['addprio'] = ks[1]
                delItem['prio'] = ks[1]
                addItem['prio'] = ks[1]
            if 2 <= len(vs):
                item['addprio'] = vs[1]
                addItem['prio'] = vs[1]
            aggrAddList.append(addItem)
            if addMode is True:
                addList.append(item)
            else:
                setList.append(item)
                aggrDelList.append(delItem)
    return {'addList': addList, 'setList': setList, 'aggrAddList': aggrAddList, 'aggrDelList': aggrDelList}

def interpreteDomainConfig(cf):
    domainconfig = getConfigOf('domain', cf, True)
    domainconfig = applyDefault(domainconfig) # must be here because following section depends on default values

    for domain, content in domainconfig.items():
        if 'ip4' in content.keys():
            domainconfig[domain]['ip4'] = domainconfig[domain]['ip4'].replace(' ', '').split(',')
        if 'ip4+' in content.keys():
            domainconfig[domain]['ip4+'] = domainconfig[domain]['ip4+'].replace(' ', '').split(',')
        if 'ip6' in content.keys():
            domainconfig[domain]['ip6'] = domainconfig[domain]['ip6'].replace(' ', '').split(',')
        if 'ip6+' in content.keys():
            domainconfig[domain]['ip6+'] = domainconfig[domain]['ip6+'].replace(' ', '').split(',')

        if 'mx' in [k.split('.')[0] for k in content.keys()]:
            mx = prioParse(content)
            domainconfig[domain]['mxSet'] = mx['setList']
            domainconfig[domain]['mxAdd'] = mx['addList']
            domainconfig[domain]['mxAggrDel'] = mx['aggrDelList']
            domainconfig[domain]['mxAggrAdd'] = mx['aggrAddList']

        if 'tlsa' in content:
            tlsa = str(domainconfig[domain]['tlsa'])
            if 'auto' == tlsa:
                tlsa = [[3, 0, 1], [3, 0, 2], [3, 1, 1], [3, 1, 2], [2, 0, 1], [2, 0, 2], [2, 1, 1], [2, 1, 2]]
            else:
                tlsa = [[int(f) for f in e] for e in tlsa.replace(' ', '').split(',')]
            domainconfig[domain]['tlsa'] = tlsa
        if 'spf' in content:
            domainconfig[domain]['spf'] = domainconfig[domain]['spf'].replace(' ', '').split(',')
        if 'spf+' in content:
            domainconfig[domain]['spf+'] = domainconfig[domain]['spf+'].replace(' ', '').split(',')
        if 'dmarc' in [k.split('.')[0] for k in content.keys()]:
            dmarc = {k.split('.')[1]: v for k, v in content.items() if 'dmarc' == k.split('.')[0]}
            domainconfig[domain]['dmarc'] = dmarc
        if 'srv' in [k.split('.')[0] for k in content.keys()]:
            srv = prioParse(content, 'srv', True, 0, True, True)
            log.debug(srv)
            srvDel = srvParseDel(srv)
            srvAdd = srvParseAdd(srv)
            domainconfig[domain]['srvAggrAdd'] = srvAdd
            domainconfig[domain]['srvAggrDel'] = srvDel
            log.debug(srvAdd)
            log.debug(srvDel)
            #domainconfig[domain]['srv'] = [{'server': v.split(':')[0], 'prio': v.split(':')[1], 'service': k.split('.')[1], 'proto': k.split('.')[2], 'port': k.split('.')[3], 'weight': k.split('.')[4]} for k, v in content.items() if 'srv' == k.split('.')[0]]
        if 'soa' in [k.split('.')[0] for k in content.keys()]:
            domainconfig[domain]['soa'] = {k.split('.')[1]: v for k, v in content.items() if 'soa' == k.split('.')[0]}
        if 'caa' in content:
            domainconfig[domain]['caa'] = [(lambda x: {'flag': x[0], 'tag': x[1], 'url': x[2]})([f for f in e.split(' ') if '' != f]) for e in domainconfig[domain]['caa'].split(',')]
        if 'caa+' in content:
            domainconfig[domain]['caa+'] = [(lambda x: {'flag': x[0], 'tag': x[1], 'url': x[2]})([f for f in e.split(' ') if '' != f]) for e in domainconfig[domain]['caa+'].split(',')]

    log.debug(domainconfig)
    return domainconfig

def interpreteDKIMConfig(cf):
    defaultDKIMConfig = {'keysize': 2048, 'keybasename': 'key', 'keylocation': '/var/lib/rspamd/dkim', 'signingconftemporaryfile': '/etc/rspamd/dkim_signing_new.conf', 'signingconftemplatefile': '/etc/rspamd/local.d/dkim_signing.conf'}
    dkimconfig = getConfigOf('dkim', cf)
    # apply general config defaults and the default section
    dkimconfig = applyDefault(dkimconfig, defaultDKIMConfig) # must be here because following section depends on default values
    return dkimconfig

def interpreteCertConfig(cf):
    defaultCertConfig = {'source': '/etc/letsencrypt/live', 'certname': 'fullchain.pem', 'keysize': 4096, 'extraflags': ''}
    certconfig = getConfigOf('certificate', cf)
    # apply general config defaults and the default section
    certconfig = applyDefault(certconfig, defaultCertConfig) # must be here because following section depends on default values



    for certSecName, content in certconfig.items():
        if 'generator' in content:
            log.debug('generator in content')
            if 'certbot' == str(content['generator']): # certbot default certificate location - overrides source config
                log.debug('certbot is generator')
                certconfig[certSecName]['source'] = '/etc/letsencrypt/live'
        if 'keysize' in content:
            certconfig[certSecName]['keysize'] = int(certconfig[certSecName]['keysize'])
        if 'extraflags' in content:
            certconfig[certSecName]['extraflags'] = content['extraflags'].replace(' ', '').split(',')
        if 'conflictingservices' in content:
            conflictingservices = content['conflictingservices'].replace(' ', '').split(',')
            if '' == conflictingservices[0]:
                conflictingservices = []
            certconfig[certSecName]['conflictingservices'] = conflictingservices
    log.debug(certconfig)
    return certconfig


def applyDefault(config, defaultConfig={}):
    default = dict(defaultConfig)
    if 'DEFAULT' in config:
        default.update(config['DEFAULT'])
    newconfig = {}
    for section, content in config.items():
        newconfig[section] = dict(default)
        newconfig[section].update(content)
    return newconfig

def getConflictingServices(certConfig):
    return {f for e in certConfig.values() if 'conflictingservices' in e for f in e['conflictingservices']}

def getConfigOf(getSection, config, domainOldStyle=False):
    resConfig = {}
    for name, content in config.items():
        section = name.split(':')
        if getSection != section[0]:
            if domainOldStyle is True:
                if '.' not in section[0]: # fallback if not domain:example.de but example.de
                    continue
            else:
                continue
        if 2 == len(section):
            secName = section[1]
        else:
            secName = 'DEFAULT'
            if domainOldStyle is True:
                if '.' in section[0]:
                    secName = section[0] # fallback if not domain:example.de but example.de
        resConfig[secName] = dict({str(k): str(v) for k, v in content.items()})
    return resConfig
