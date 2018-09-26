#!/usr/bin/env python
# -*- encoding: UTF8 -*-

#######################################################################
#
#    Copyright (c) 2018 Stefan Helmert <stefan.helmert@t-online.de>
#
#######################################################################

from simpleloggerplus import simpleloggerplus as log

def applyDefault(config, defaultConfig={}):
    default = dict(defaultConfig)
    if 'DEFAULT' in config:
        default.update(config['DEFAULT'])
    newconfig = {}
    for section, content in config.items():
        newconfig[section] = dict(default)
        newconfig[section].update(content)
    return newconfig

# Default handling
# DEFAULT section overwritten by handler default configuration overwr. by explicit configuration


def interpreteConfig(cr, sh):
    defaultCertConfig = {'certname': 'fullchain.pem', 'keysize': 4096, 'extraflags': ''}
    certconfig = cr.getRawConfigOf('cert')
    # apply general config defaults and the default section
    certconfig = applyDefault(certconfig, defaultCertConfig) # must be here because following section depends on default values

    for certSecName, content in certconfig.items():
        content = dict(content)
        if 'handler' in content:
            log.debug('handler in content')
            handlers = content['handler'].split('/')
            handler = __import__('modules.cert.handler'+str(handlers[0]), fromlist=('modules','cert'))
            certconfig[certSecName].update(handler.defaultCertConfig)
            certconfig[certSecName]['caa'] = {'url': 'letsencrypt.org', 'flag': '0', 'tag': 'issue'}
            if 1 < len(handlers):
                if 'letsencrypt' != handlers[1]:
                    certconfig[certSecName]['caa'] = ''
        if 'keysize' in content:
            certconfig[certSecName]['keysize'] = int(content['keysize'])
        if 'extraflags' in content:
            certconfig[certSecName]['extraflags'] = [e for e in content['extraflags'].replace(' ', '').split(',') if len(e) > 0]
        if 'conflictingservices' in content:
            conflictingservices = content['conflictingservices'].replace(' ', '').split(',')
            if '' == conflictingservices[0]:
                conflictingservices = []
            certconfig[certSecName]['conflictingservices'] = conflictingservices
    log.debug(certconfig)
    cr.updateConfig({'cert': certconfig})
    return certconfig

