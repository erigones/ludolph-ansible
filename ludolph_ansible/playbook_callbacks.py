# -*- coding: utf-8 -*-
"""
This file is part of Ludolph: Ansible plugin
Copyright (C) 2015 Erigones, s. r. o.

See the LICENSE file for copying permission.
"""
from __future__ import absolute_import

import fnmatch

from six import text_type, iteritems
from ansible import constants
from ansible import utils
from ansible.module_utils import basic
from ansible.utils.unicode import to_bytes


# noinspection PyUnusedLocal
def display(msg, color=None, stderr=False, screen_only=False, log_only=False, runner=None):
    print(msg)


class AggregateStats(object):
    """holds stats about per-host activity during playbook runs"""
    def __init__(self):
        self.processed = {}
        self.failures = {}
        self.ok = {}
        self.dark = {}
        self.changed = {}
        self.skipped = {}

    def _increment(self, what, host):
        """helper function to bump a statistic"""
        self.processed[host] = 1
        prev = (getattr(self, what)).get(host, 0)
        getattr(self, what)[host] = prev + 1

    def compute(self, runner_results, setup=False, poll=False, ignore_errors=False):
        """walk through all results and increment stats"""
        for (host, value) in iteritems(runner_results.get('contacted', {})):
            if not ignore_errors and (
                        ('failed' in value and bool(value['failed'])) or
                        ('failed_when_result' in value and [value['failed_when_result']] or
                            ['rc' in value and value['rc'] != 0])[0]
            ):
                self._increment('failures', host)
            elif 'skipped' in value and bool(value['skipped']):
                self._increment('skipped', host)
            elif 'changed' in value and bool(value['changed']):
                if not setup and not poll:
                    self._increment('changed', host)
                self._increment('ok', host)
            else:
                if not poll or ('finished' in value and bool(value['finished'])):
                    self._increment('ok', host)

        for (host, value) in iteritems(runner_results.get('dark', {})):
            self._increment('dark', host)

    def summarize(self, host):
        """return information about a particular host"""
        return {
            'ok': self.ok.get(host, 0),
            'failures': self.failures.get(host, 0),
            'unreachable': self.dark.get(host, 0),
            'changed': self.changed.get(host, 0),
            'skipped': self.skipped.get(host, 0)
        }


def banner(msg):
    width = 78 - len(msg)

    if width < 3:
        width = 3
    filler = "*" * width

    return "\n%s %s " % (msg, filler)


# noinspection PyUnusedLocal
class PlaybookRunnerCallbacks(object):
    """callbacks used for Runner() from ludolph playbook command"""
    runner = None

    # noinspection PyShadowingNames
    def __init__(self, stats, verbose=None, display=display):
        if verbose is None:
            verbose = utils.VERBOSITY

        self.verbose = verbose
        self.display = display
        self.stats = stats
        self._async_notified = {}

    def on_unreachable(self, host, results):
        if self.runner.delegate_to:
            host = '%s -> %s' % (host, self.runner.delegate_to)

        item = None

        if type(results) == dict:
            item = results.get('item', None)
            if isinstance(item, text_type):
                item = utils.unicode.to_bytes(item)
            results = basic.json_dict_unicode_to_bytes(results)
        else:
            results = utils.unicode.to_bytes(results)

        host = utils.unicode.to_bytes(host)

        if item:
            msg = "fatal: [%s] => (item=%s) => %s" % (host, item, results)
        else:
            msg = "fatal: [%s] => %s" % (host, results)

        self.display(msg, color='red', runner=self.runner)

    def on_failed(self, host, results, ignore_errors=False):
        if self.runner.delegate_to:
            host = '%s -> %s' % (host, self.runner.delegate_to)

        results2 = results.copy()
        results2.pop('invocation', None)

        item = results2.get('item', None)
        parsed = results2.get('parsed', True)
        module_msg = ''

        if not parsed:
            module_msg = results2.pop('msg', None)

        stderr = results2.pop('stderr', None)
        stdout = results2.pop('stdout', None)
        returned_msg = results2.pop('msg', None)

        if item:
            msg = "failed: [%s] => (item=%s) => %s" % (host, item, utils.jsonify(results2))
        else:
            msg = "failed: [%s] => %s" % (host, utils.jsonify(results2))

        self.display(msg, color='red', runner=self.runner)

        if stderr:
            self.display("stderr: %s" % stderr, color='red', runner=self.runner)
        if stdout:
            self.display("stdout: %s" % stdout, color='red', runner=self.runner)
        if returned_msg:
            self.display("msg: %s" % returned_msg, color='red', runner=self.runner)
        if not parsed and module_msg:
            self.display(module_msg, color='red', runner=self.runner)
        if ignore_errors:
            self.display("...ignoring", color='cyan', runner=self.runner)

    def on_ok(self, host, host_result):
        if self.runner.delegate_to:
            host = '%s -> %s' % (host, self.runner.delegate_to)

        item = host_result.get('item', None)
        host_result2 = host_result.copy()
        host_result2.pop('invocation', None)
        verbose_always = host_result2.pop('verbose_always', False)
        changed = host_result.get('changed', False)
        ok_or_changed = 'ok'

        if changed:
            ok_or_changed = 'changed'

        # show verbose output for non-setup module results if --verbose is used
        msg = ''

        if (not self.verbose or host_result2.get("verbose_override", None) is not None) and not verbose_always:
            if item:
                msg = "%s: [%s] => (item=%s)" % (ok_or_changed, host, item)
            else:
                if 'ansible_job_id' not in host_result or 'finished' in host_result:
                    msg = "%s: [%s]" % (ok_or_changed, host)
        else:
            # verbose ...
            if item:
                msg = "%s: [%s] => (item=%s) => %s" % (ok_or_changed, host, item, utils.jsonify(host_result2,
                                                                                                format=verbose_always))
            else:
                if 'ansible_job_id' not in host_result or 'finished' in host_result2:
                    msg = "%s: [%s] => %s" % (ok_or_changed, host, utils.jsonify(host_result2, format=verbose_always))

        if msg != '':
            if not changed:
                self.display(msg, color='green', runner=self.runner)
            else:
                self.display(msg, color='orange', runner=self.runner)

        if constants.COMMAND_WARNINGS and 'warnings' in host_result2 and host_result2['warnings']:
            for warning in host_result2['warnings']:
                self.display("warning: %s" % warning, color='purple', runner=self.runner)

    def on_skipped(self, host, item=None):
        if self.runner.delegate_to:
            host = '%s -> %s' % (host, self.runner.delegate_to)

        if constants.DISPLAY_SKIPPED_HOSTS:
            if item:
                msg = "skipping: [%s] => (item=%s)" % (host, item)
            else:
                msg = "skipping: [%s]" % host

            self.display(msg, color='cyan', runner=self.runner)

    def on_no_hosts(self):
        self.display("FATAL: no hosts matched or all hosts have already failed -- aborting\n", color='red',
                     runner=self.runner)

    def on_async_poll(self, host, res, jid, clock):
        if jid not in self._async_notified:
            self._async_notified[jid] = clock + 1

        if self._async_notified[jid] > clock:
            self._async_notified[jid] = clock
            msg = "<job %s> polling, %ss remaining" % (jid, clock)
            self.display(msg, color='cyan', runner=self.runner)

    def on_async_ok(self, host, res, jid):
        msg = "<job %s> finished on %s" % (jid, host)
        self.display(msg, color='cyan', runner=self.runner)

    def on_async_failed(self, host, res, jid):
        msg = "<job %s> FAILED on %s" % (jid, host)
        self.display(msg, color='red', stderr=True, runner=self.runner)

    def on_file_diff(self, host, diff):
        self.display(utils.get_diff(diff), runner=self.runner)


# noinspection PyMethodMayBeStatic
class PlaybookCallbacks(object):
    """playbook.py callbacks used by ludolph playbook command"""
    # noinspection PyShadowingNames
    def __init__(self, verbose=False, display=display):
        self.verbose = verbose
        self.display = display

    def on_start(self):
        pass

    def on_notify(self, host, handler):
        pass

    def on_no_hosts_matched(self):
        self.display("skipping: no hosts matched", color='cyan')

    def on_no_hosts_remaining(self):
        self.display("\nFATAL: all hosts have already failed -- aborting", color='red')

    # noinspection PyAttributeOutsideInit
    def on_task_start(self, name, is_conditional):
        name = utils.unicode.to_bytes(name)
        msg = "TASK: [%s]" % name

        if is_conditional:
            msg = "NOTIFIED: [%s]" % name

        if hasattr(self, 'start_at'):
            self.start_at = utils.unicode.to_bytes(self.start_at)

            # noinspection PyUnresolvedReferences
            if name == self.start_at or fnmatch.fnmatch(name, self.start_at):
                # we found out match, we can get rid of this now
                del self.start_at
            elif self.task.role_name:
                # handle tasks prefixed with rolenames
                actual_name = name.split('|', 1)[1].lstrip()
                if actual_name == self.start_at or fnmatch.fnmatch(actual_name, self.start_at):
                    del self.start_at

        if hasattr(self, 'start_at'):  # we still have start_at so skip the task
            self.skip_task = True
        elif hasattr(self, 'step') and self.step:
            self.skip_task = True
        else:
            self.skip_task = False
            self.display(banner(msg))

    def on_vars_prompt(self, varname, private=True, prompt=None, encrypt=None, confirm=False, salt_size=None,
                       salt=None, default=None):
        pass

    def on_setup(self):
        self.display(banner("GATHERING FACTS"))

    def on_import_for_host(self, host, imported_file):
        msg = "%s: importing %s" % (host, imported_file)
        self.display(msg, color='cyan')

    def on_not_import_for_host(self, host, missing_file):
        msg = "%s: not importing file: %s" % (host, missing_file)
        self.display(msg, color='cyan')

    def on_play_start(self, name):
        self.display(banner("PLAY [%s]" % name))

    def on_stats(self, stats):
        pass
