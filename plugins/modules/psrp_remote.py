#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r'''
---
module: psrp_remote
author: Nic McElroy
short_description: Invoke commands over PSRP directly
description:
- Invoke commands over PSRP in the context of an ansible module, compatible with JEA RemoteRestricted and RestrictedLanguage

options:
  host:
    description:
    - The hostname of the systems you want to invoke the command on
    required: true
  script:
    description:
    - The script you want to invoke on the remote host, can be multiline
    required: false
  test_script:
    description:
    - The script to determine if the system is in the desired state already, must return a boolean true or false
    required: false
  configuration_name:
    description:
    - The PSRP configuration name to connect to
    required: false
  expect_json:
    description:
    - Set whether the module should attempt to deserialise directly from json, useful as pypsrp has a limited deserialiser, set your script to output json to use this
    required: false
requirements:
- pypsrp
'''

import json
import pypsrp
from ansible.module_utils.basic import AnsibleModule
from pypsrp.powershell import PowerShell, RunspacePool
from pypsrp.wsman import WSMan


class PSRP_Wrapper():
    def __init__(self, host, configuration_name="Microsoft.PowerShell"):
        self.host = host
        self.configuration_name = configuration_name

    def invoke_script(self, script, expect_json=False):
        wsman = WSMan(self.host, auth="kerberos", cert_validation=False, ssl=True)
        with RunspacePool(wsman, configuration_name=self.configuration_name) as pool:
            ps = PowerShell(pool)
            ps.add_script(script)
            ps.invoke()
            if ps.had_errors:
                error_messages = []
                for i in ps.streams.error:
                    error_messages.append(i.message)
                raise RuntimeError(error_messages)
            else:
                if expect_json:
                    output = [json.loads(x) for x in ps.output]
                else:
                    output = PSRP_Wrapper._convertto_json_compatible(ps.output)

                stream_names =  ["debug", "error", "information", "verbose", "warning"]
                streams = dict()
                for i in stream_names:
                    streams[i] = []
                    for j in getattr(ps.streams, i):
                        streams[i].append(j.message)
                return {
                     "output": output,
                     "streams": streams
                }


    @staticmethod
    def _convertto_json_compatible(complex_object):
        if isinstance(complex_object, list):
            pyobject = []
            for i in complex_object:
                if isinstance(i, pypsrp.complex_objects.GenericComplexObject):
                    pyobject.append(PSRP_Wrapper._convertto_json_compatible(i))
                elif isinstance(i, list):
                    pyobject.append(PSRP_Wrapper._convertto_json_compatible(i))
                else:
                    pyobject.append(i)
        else:
            pyobject = dict()
            # print(type(complex_object.adapted_properties))
            for k,v in complex_object.adapted_properties.items():
                if isinstance(v, pypsrp.complex_objects.GenericComplexObject):
                    pyobject[k] = PSRP_Wrapper._convertto_json_compatible(v)
                elif isinstance(v, list):
                    pyobject[k] = PSRP_Wrapper._convertto_json_compatible(v)
                else:
                    pyobject[k] = v
            for k,v in complex_object.extended_properties.items():
                if isinstance(v, pypsrp.complex_objects.GenericComplexObject):
                    pyobject[k] = PSRP_Wrapper._convertto_json_compatible(v)
                elif isinstance(v, list):
                    pyobject[k] = PSRP_Wrapper._convertto_json_compatible(v)
                else:
                    pyobject[k] = v
        return pyobject


def main():

    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', required=True),
            script=dict(type='str', required=True),
            test_script=dict(type='str'),
            configuration_name=dict(type='str', default="Microsoft.PowerShell"),
            expect_json = dict(type='bool', default=False)
        )
    )

    shell = PSRP_Wrapper(host=module.params['host'], configuration_name=module.params['configuration_name'])
    test_result = False
    result = {
        "changed": False
    }

    try:
        if module.params['test_script']:
            test = shell.invoke_script(module.params['test_script'], expect_json=False)
            result['test_output'] = test
            test_result = test['output'][0]
        if not isinstance(test_result, bool):
            raise ValueError(f"Type of test result ")
        else:
            pass
        if not test_result:
            result['changed'] = True
            invoke_result = shell.invoke_script(module.params['script'], expect_json=module.params['expect_json'])
            result.update(invoke_result)
        else:
            pass
        #print(result)
        module.exit_json(**result)

    except Exception as e:
        result['msg'] = str(e)
        module.fail_json(**result)


if __name__ == '__main__':
    main()