# (C) 2012, Michael DeHaan, <michael.dehaan@gmail.com>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    callback: kc_operation_log
    type: notification
    short_description: write playbook output to kc api
    version_added: historical
    description:
      - This callback writes playbook output to kc api
    requirements:
     - Whitelist in configuration
     - definition operation_log_uuid in inventory vars
'''

import os
import requests
import time
import json

from ansible.utils.path import makedirs_safe
from ansible.module_utils._text import to_bytes
from ansible.plugins.callback import CallbackBase
from ansible.errors import AnsibleError

# NOTE: in Ansible 1.2 or later general logging is available without
# this plugin, just set ANSIBLE_LOG_PATH as an environment variable
# or log_path in the DEFAULTS section of your ansible configuration
# file.  This callback is an example of per hosts logging for those
# that want it.

try:
    import requests
except ImportError:
    raise AnsibleError("can not find module of requests")

class CallbackModule(CallbackBase):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'kc_operation_log'
    CALLBACK_NEEDS_WHITELIST = True
    TIME_FORMAT = "%b %d %Y %H:%M:%S"

    ## KC callback api config
    REQUEST_URI = 'http://localhost:8087/api/ansible_plugin/callback/kc_operation_log'
    REQUEST_HEADER = {
        'Accept': 'application/vnd.apache.kylin-v4+json',
        'Accept-Language': 'en',
        'Content-Type': 'application/json;charset=utf-8',
        'Authorization': ''
    }
    ## Filter the specified field in the result log.
    FILTER_LOG_FIELD = ['stdout_lines', 'stderr_lines', '_ansible_no_log', 'exception', 'invocation']

    def __init__(self):
        # init vars of kc need, and used in on playbook end.
        self.playbook_failed_result = {}
        self.playbook_progress = {}
        self.playbook_progress['start_host'] = []
        self.playbook_progress['end_host'] = []

        super(CallbackModule, self).__init__()

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)

    def v2_playbook_on_play_start(self, play):
        self.variable_manager = play.get_variable_manager()

    def runner_on_failed(self, host, res, ignore_errors=True):
        ## init a result list of failed
        if host not in self.playbook_failed_result:
            self.playbook_failed_result[host] = {}
        if 'FAILED' not in self.playbook_failed_result[host]:
            self.playbook_failed_result[host]['FAILED'] = []

        self.playbook_failed_result[host]['FAILED'].append(self.filter_res(res))

    def runner_on_unreachable(self, host, res):
        ## init a result list of unreachable
        if host not in self.playbook_failed_result:
            self.playbook_failed_result[host] = {}
        if 'UNREACHABLE' not in self.playbook_failed_result[host]:
            self.playbook_failed_result[host]['UNREACHABLE'] = []

        self.playbook_failed_result[host]['UNREACHABLE'].append(self.filter_res(res))

    def playbook_on_stats(self, stats):
        if self.playbook_failed_result:
            host_1 = list(stats.processed.keys())[0]
            self.operation_log_uuid = self.variable_manager.get_vars()['hostvars'][host_1]['operation_log_uuid']
            self.my_debug_log('playbook_on_stats: operationLogId ===> ' + self.operation_log_uuid)
            self.my_debug_log('playbook_on_stats: playbook_failed_result ===> ' + str(self.playbook_failed_result))

            self.send_callback_request(self.playbook_failed_result)

    def send_callback_request(self, jsonMsg):
        data_dict = {
            "operationLogUuid": str(self.operation_log_uuid),
            "failedMessage": jsonMsg
        }
        res = requests.post(url=self.REQUEST_URI, headers=self.REQUEST_HEADER, data=json.dumps(data_dict))
        self.my_debug_log('send_callback_request: res ===>' + str(res))

    def filter_res(self, res):
        for key in self.FILTER_LOG_FIELD:
            if key in res:
                res.pop(key)
        return res

    def my_debug_log(self, my_msg):
        debug_path = "/opt/kyligence_cloud/test"
        path = os.path.join(debug_path, "kc_operation_log-debug.log")
        now = time.strftime(self.TIME_FORMAT, time.localtime())
        if not os.path.exists(debug_path):
            makedirs_safe(debug_path)
        msg = to_bytes("%(now)s DEBUG ==> kc_operation_log: %(data)s\n\n" % dict(now=now, data=my_msg))

        with open(path, "ab") as fd:
            fd.write(msg)
