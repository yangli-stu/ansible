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
     - some config in inventory vars, such as kc api, header, operationLogId
'''

import os
import requests
import time
import json

from ansible.utils.path import makedirs_safe
from ansible.module_utils._text import to_bytes
from ansible.module_utils.common._collections_compat import MutableMapping
from ansible.parsing.ajson import AnsibleJSONEncoder
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
    MSG_FORMAT = "%(now)s - %(category)s - %(data)s\n\n"

    def __init__(self):
        # init vars of kc need, and used in on playbook end.
        self.playbook_error_result = {}
        self.playbook_progress = {}
        self.playbook_progress['start_host'] = []
        self.playbook_progress['end_host'] = []

        super(CallbackModule, self).__init__()

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)

    def v2_playbook_on_play_start(self, play):
        self.variable_manager = play.get_variable_manager()

    def runner_on_failed(self, host, res, ignore_errors=False):
        self.playbook_error_result[host] = {}
        self.playbook_error_result[host]['FAILED'] = self.filter_res(res)
        # self.log(host, 'FAILED', res)

    def runner_on_unreachable(self, host, res):
        self.playbook_error_result[host] = {}
        self.playbook_error_result[host]['UNREACHABLE'] = self.filter_res(res)
        # self.log(host, 'UNREACHABLE', res)

    def playbook_on_stats(self, stats):
        self.my_log(self.playbook_error_result)
        self.send_kc_request(self.playbook_error_result)

    def send_kc_request(self, jsonMsg):
        url = 'http://localhost:8087/api/ansible_plugin/callback/kc_operation_log'
        header_dict = {
            'Content-Type': 'application/json;charset=utf-8'
        }
        data_dict = {
            'operationLogId': "1234",
            'msg': jsonMsg
        }
        res = requests.put(url=url, headers=header_dict, data=json.dumps(data_dict))
        self.my_log(res)

    def filter_res(self, res):
        # TODO: filter
        res.pop('stdout_lines')
        res.pop('stderr_lines')
        res.pop('_ansible_no_log')
        return res

    def my_log(self, my_msg):
        my_path = "/opt/kyligence_cloud/test"
        path = os.path.join(my_path, "log_file")
        now = time.strftime(self.TIME_FORMAT, time.localtime())
        if not os.path.exists(my_path):
            makedirs_safe(my_path)

        msg = to_bytes("%(now)s ==> my_msg: %(data)s\n\n" % dict(now=now, data=my_msg))

        with open(path, "ab") as fd:
            fd.write(msg)

    def log(self, host, category, data):
        host_vars = self.variable_manager.get_vars()['hostvars'][host]

        self.log_folder = host_vars['log_path']
        if not os.path.exists(self.log_folder):
            makedirs_safe(self.log_folder)

        var_that_i_want = host_vars['ssh_user']

        if isinstance(data, MutableMapping):
            if '_ansible_verbose_override' in data:
                # avoid logging extraneous data
                data = 'omitted'
            else:
                data = data.copy()
                invocation = data.pop('invocation', None)
                data = json.dumps(data, cls=AnsibleJSONEncoder)
                if invocation is not None:
                    data = json.dumps(invocation) + " bowen_test_log [%s] => %s " % (var_that_i_want, data)

        path = os.path.join(self.log_folder, host)
        now = time.strftime(self.TIME_FORMAT, time.localtime())

        msg = to_bytes(self.MSG_FORMAT % dict(now=now, category=category, data=data))
        with open(path, "ab") as fd:
            fd.write(msg)

