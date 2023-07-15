"""
A module for externally creating code templates for the DiamondFire Minecraft server.

By Amp
7/14/2023
"""

import base64
import gzip
import socket
import time
import json
import os
from difflib import get_close_matches
from typing import Tuple
from dfpyre.items import *

COL_WARN = '\x1b[33m'
COL_RESET = '\x1b[0m'
COL_SUCCESS = '\x1b[32m'
COL_ERROR = '\x1b[31m'

CODEBLOCK_DATA_PATH = 'dfpyre/data/data.json'

VARIABLE_TYPES = {'txt', 'num', 'item', 'loc', 'var', 'snd', 'part', 'pot', 'g_val', 'vec'}
TEMPLATE_STARTERS = {'event', 'entity_event', 'func', 'process'}


def _warn(message):
    print(f'{COL_WARN}! WARNING ! {message}{COL_RESET}')


def _loadCodeblockData():
    tagData = {}
    if os.path.exists(CODEBLOCK_DATA_PATH):
        with open(CODEBLOCK_DATA_PATH, 'r') as f:
            tagData = json.load(f)
    else:
        _warn('data.json not found -- Item tags and error checking will not work.')
        return ({}, set(), set())
    return (
        tagData,
        set(tagData.keys()),
        set(tagData['extras'].keys())
    )

TAGDATA, TAGDATA_KEYS, TAGDATA_EXTRAS_KEYS = _loadCodeblockData()

def sendToDf(templateCode: str, name: str='Unnamed Template'):
    """
    Sends a template to DiamondFire via recode item api.

    :param str templateCode: The code for the template in base64 format.
    :param str name: The name of the template.
    """
    itemName = 'pyre Template - ' + name
    templateData = f"{{\"name\":\"{itemName}\",\"data\":\"{templateCode}\"}}"
    data = {"type": "template", "source": f"pyre - {name}","data": templateData}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', 31372))
    except ConnectionRefusedError:
        print(f'{COL_ERROR}Could not connect to recode item API. (Minecraft is not open or something else has gone wrong){COL_RESET}')
        s.close()
        return
    
    s.send((str(data) + '\n').encode())
    received = json.loads(s.recv(1024).decode())
    status = received['status']
    if status == 'success':
        print(f'{COL_SUCCESS}Template sent to client successfully.{COL_RESET}')
    else:
        error = received['error']
        print(f'{COL_ERROR}Error sending template: {error}{COL_RESET}')
    s.close()
    time.sleep(0.5)


class DFTemplate:
    """
    Represents a DiamondFire code template.
    """
    def __init__(self):
        self.commands = []
        self.closebracket = None
        self.definedVars = {}


    def build(self) -> Tuple[str, str]:
        """
        Build this template.

        :return: Tuple containing compressed template code and template name.
        """
        mainDict = {'blocks': []}
        for cmd in self.commands:
            block = {'args': {'items': []}}
            
            # add keys from cmd.data
            for key in cmd.data.keys():
                block[key] = cmd.data[key]

            # bracket data
            if cmd.data.get('direct') != None:
                block['direct'] = cmd.data['direct']
                block['type'] = cmd.data['type']
            
            # add target if necessary
            if cmd.data.get('block') != 'event':
                if cmd.target != 'Default':
                    block['target'] = cmd.target
            

            # add items into args part of dictionary
            slot = 0
            if cmd.args:  # tuple isnt empty
                for arg in cmd.args[0]:
                    app = None
                    if arg.type in VARIABLE_TYPES:
                        app = arg.format(slot)
                        block['args']['items'].append(app)
                
                    slot += 1
            
            # set tags
            blockType = cmd.data.get('block')
            tags = None
            if blockType in TAGDATA_EXTRAS_KEYS:
                tags = TAGDATA['extras'][blockType]
            elif blockType in TAGDATA_KEYS:
                tags = TAGDATA[blockType].get(cmd.name)
                if tags is None:
                    close = get_close_matches(cmd.name, TAGDATA[blockType].keys())
                    if close:
                        _warn(f'Code block name "{cmd.name}" not recognized. Did you mean "{close[0]}"?')
                    else:
                        _warn(f'Code block name "{cmd.name}" not recognized. Try spell checking or re-typing without spaces.')
            if tags is not None:
                items = block['args']['items']
                if len(items) > 27:
                    block['args']['items'] = items[:(26-len(tags))]  # trim list
                block['args']['items'].extend(tags)  # add tags to end

            mainDict['blocks'].append(block)

        print(f'{COL_SUCCESS}Template built successfully.{COL_RESET}')

        templateName = 'Unnamed'
        if not mainDict['blocks'][0]['block'] in TEMPLATE_STARTERS:
            _warn('Template does not start with an event, function, or process.')
        else:
            try:
                templateName = mainDict['blocks'][0]['block'] + '_' + mainDict['blocks'][0]['action']
            except KeyError:
                templateName = mainDict['blocks'][0]['data']
        
        return self._compress(str(mainDict)), templateName
    

    def _compress(self, jsonString: str) -> str:
        compressedString = gzip.compress(jsonString.encode('utf-8'))
        return str(base64.b64encode(compressedString))[2:-1]
    

    def buildAndSend(self):
        """
        Builds this template and sends it to DiamondFire automatically.
        """
        templateCode, templateName = self.build()
        sendToDf(templateCode, name=templateName)
    

    def _convertDataTypes(self, lst):
        retList = []
        for element in lst:
            if type(element) in {int, float}:
                retList.append(num(element))
            elif type(element) == str:
                if element[0] == '^':
                    retList.append(self.definedVars[element[1:]])
                else:
                    retList.append(text(element))
            else:
                retList.append(element)
        return tuple(retList)
    

    def clear(self):
        """
        Clears this template's data.
        """
        self.__init__()
    

    def _openbracket(self, btype: str='norm'):
        bracket = CodeBlock('Bracket', data={'id': 'bracket', 'direct': 'open', 'type': btype})
        self.commands.append(bracket)
        self.closebracket = btype
    

    # command methods
    def playerEvent(self, name: str):
        cmd = CodeBlock(name, data={'id': 'block', 'block': 'event', 'action': name})
        self.commands.append(cmd)
    

    def entityEvent(self, name: str):
        cmd = CodeBlock(name, data={'id': 'block', 'block': 'entity_event', 'action': name})
        self.commands.append(cmd)
    

    def function(self, name: str):
        cmd = CodeBlock('function', data={'id': 'block', 'block': 'func', 'data': name})
        self.commands.append(cmd)
    

    def process(self, name: str):
        cmd = CodeBlock('process', data={'id': 'block', 'block': 'process', 'data': name})
        self.commands.append(cmd)
    

    def callFunction(self, name: str, parameters={}):
        if parameters:
            for key in parameters.keys():
                self.setVariable('=', var(key, scope='local'), parameters[key])
        
        cmd = CodeBlock('call_func', data={'id': 'block', 'block': 'call_func', 'data': name})
        self.commands.append(cmd)
    

    def startProcess(self, name: str):
        cmd = CodeBlock('start_process', data={'id': 'block', 'block': 'start_process', 'data': name})
        self.commands.append(cmd)


    def playerAction(self, name: str, *args, target: str='Default'):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, target=target, data={'id': 'block', 'block': 'player_action', 'action': name})
        self.commands.append(cmd)
    

    def gameAction(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'game_action', 'action': name})
        self.commands.append(cmd)
    

    def entityAction(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'entity_action', 'action': name})
        self.commands.append(cmd)
    

    def ifPlayer(self, name: str, *args, target: str='Default'):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, target=target, data={'id': 'block', 'block': 'if_player', 'action': name})
        self.commands.append(cmd)
        self._openbracket()
    

    def ifVariable(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'if_var', 'action': name})
        self.commands.append(cmd)
        self._openbracket()
    

    def ifGame(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'if_game', 'action': name})
        self.commands.append(cmd)
        self._openbracket()
    

    def ifEntity(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'if_entity', 'action': name})
        self.commands.append(cmd)
        self._openbracket()


    def else_(self):
        cmd = CodeBlock('else', data={'id': 'block', 'block': 'else'})
        self.commands.append(cmd)
        self._openbracket()
    

    def repeat(self, name: str, *args, subAction: str=None):
        args = self._convertDataTypes(args)
        data = {'id': 'block', 'block': 'repeat', 'action': name}
        if subAction is not None:
            data['subAction'] = subAction
        cmd = CodeBlock(name, args, data=data)
        self.commands.append(cmd)
        self._openbracket('repeat')


    def bracket(self, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock('Bracket', data={'id': 'bracket', 'direct': 'close', 'type': self.closebracket})
        self.commands.append(cmd)
    

    def control(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'control', 'action': name})
        self.commands.append(cmd)
    

    def selectObject(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'select_obj', 'action': name})
        self.commands.append(cmd)
    

    def setVariable(self, name: str, *args):
        args = self._convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'set_var', 'action': name})
        self.commands.append(cmd)
    

    # extra methods
    def return_(self, returndata={}):
        for key in returndata:
            self.setVariable('=', var(key, scope='local'), returndata[key])
        self.control('Return')
    

    def define_(self, name: str, value=0, scope: str='unsaved', createSetVar: bool=True):
        if createSetVar:
            self.setVariable('=', var(name, scope=scope), value)
        self.definedVars[name] = var(name, scope=scope)


class CodeBlock:
    def __init__(self, name: str, *args, target: str='Default', data={}):
        self.name = name
        self.args = args
        self.target = target
        self.data = data