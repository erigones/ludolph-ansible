# -*- coding: utf-8 -*-
"""
This file is part of Ludolph: Ansible plugin
Copyright (C) 2015 Erigones, s. r. o.

See the LICENSE file for copying permission.
"""
from __future__ import absolute_import
from __future__ import print_function
from os import path

from ludolph.command import CommandError, PermissionDenied, command
from ludolph.plugins.plugin import LudolphPlugin

from ansible import utils
from ansible.errors import AnsibleError
from ansible.inventory import Inventory
from ansible.playbook import PlayBook
from ansible.playbook.play import Play

from . import __version__
from .playbook_callbacks import banner, AggregateStats, PlaybookCallbacks, PlaybookRunnerCallbacks


def _file(value):
    file_path = path.abspath(path.realpath(value))

    if not path.isfile(file_path):
        raise ValueError('File "%s" does not exist' % value)

    return file_path


def _bool(value):
    if not value or str(value).lower() in ('no', 'false'):
        return False
    else:
        return True


def colorize(msg, color):
    msg2 = msg.rstrip(' ')
    end_spaces = len(msg) - len(msg2)

    return '%%{color:%s}%s%%' % (color, msg2.lstrip()) + ' ' * end_spaces


def stringc(msg, color):
    if '\n' in msg:
        lines = msg.split('\n')
        lines[0] = colorize(lines[0], color)
        return '\n'.join(lines)
    else:
        return colorize(msg, color)


def hostcolor(host, stats):
    host = "%-37s" % host

    if stats['failures'] != 0 or stats['unreachable'] != 0:
        color = 'red'
    elif stats['changed'] != 0:
        color = 'orange'
    else:
        color = 'green'

    return stringc(host, color)


class DisplayCallback(object):
    """
    Display task output.
    """
    buffer = []

    def __init__(self, display_fun=print):
        self.display_fun = display_fun

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def process_msg(self, msg, color=None, **kwargs):
        if color:
            msg = stringc(msg, color)

        return msg

    def save(self, msg, **kwargs):
        self.buffer.append(self.process_msg(msg, **kwargs))

    def flush(self):
        if self.buffer:
            self.display_fun('\n'.join(self.buffer))
            del self.buffer[:]

    def display(self, msg, flush=True, **kwargs):
        if flush:
            self.flush()
            self.display_fun(self.process_msg(msg, **kwargs))
        else:
            self.save(msg, **kwargs)

    __call__ = display


class Playbook(LudolphPlugin):
    """
    Run ansible playbooks from ludolph.
    """
    __version__ = __version__
    _available_options = (
        ('forks', int),
        ('check', _bool),
        ('private_key_file', _file),
    )

    def __post_init__(self):
        config = self.config
        basedir = path.abspath(path.realpath(config.get('basedir', '')))

        if not basedir:
            raise RuntimeError('basedir is not set in ludolph_ansible.playbook plugin configuration')

        if not path.isdir(basedir):
            raise RuntimeError('basedir "%s" does not exist' % basedir)

        self.basedir = basedir
        self.options = {}
        self.playbooks = {}
        self.admin_required = _bool(config.get('restrict_playbooks', False))
        self.restrict_playbooks = _bool(config.get('restrict_playbooks', False))

        inventory = config.get('inventory', None)
        if inventory:
            if not path.isfile(inventory):
                raise RuntimeError('inventory "%s" does not exist' % inventory)
            self.options['inventory'] = Inventory(inventory)
        else:
            inventory = path.join(basedir, 'hosts.cfg')
            if path.exists(inventory):
                self.options['inventory'] = Inventory(inventory)

        playbooks = config.get('playbooks', None)
        if playbooks:
            try:
                for pb_mapping in playbooks.strip().split(','):
                    pb_alias, pb_file = pb_mapping.split(':')
                    self.playbooks[pb_alias.strip()] = pb_file.strip()
            except (ValueError, TypeError):
                raise RuntimeError('invalid value for playbooks option in '
                                   'ludolph_ansible.playbook plugin configuration')

        for opt_name, check_fun in self._available_options:
            opt_value = config.get(opt_name, None)

            if opt_value is not None:
                try:
                    opt_value = check_fun(opt_value)
                except ValueError:
                    raise RuntimeError('invalid value for %s option in '
                                       'ludolph_ansible.playbook plugin configuration' % opt_name)
                else:
                    self.options[opt_name] = opt_value

    def _get_callbacks(self, msg):
        stats = AggregateStats()
        display = DisplayCallback(lambda text: self.xmpp.msg_reply(msg, text, preserve_msg=True))

        return {
            'stats': stats,
            'callbacks': PlaybookCallbacks(verbose=utils.VERBOSITY, display=display),
            'runner_callbacks': PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY, display=display.save),
        }

    @staticmethod
    def _get_playbook_data(playbook):
        return (Play(playbook, play_ds, play_basedir)
                for play_ds, play_basedir in zip(playbook.playbook, playbook.play_basedirs))

    def _get_playbook(self, msg, pb_name):
        """Get playbook by name"""
        if self.admin_required and not self.xmpp.is_jid_admin(self.xmpp.get_jid(msg)):
            raise PermissionDenied

        try:
            pb_name = self.playbooks[pb_name]
        except KeyError:
            if self.restrict_playbooks:
                raise CommandError('Invalid playbook name: **%s**' % pb_name)

        if not pb_name.endswith('.yml'):
            pb_name += '.yml'

        pb_path = path.abspath(path.realpath(path.join(self.basedir, pb_name)))

        if not pb_path.startswith(self.basedir + path.sep):
            raise CommandError('Invalid playbook name: **%s**' % pb_name)

        if not path.isfile(pb_path):
            raise CommandError('Playbook **%s** not found' % pb_name)

        options = self._get_callbacks(msg)
        options.update(self.options)

        return PlayBook(playbook=pb_path, **options)

    @command
    def apb(self, msg, playbook, *args):
        """
        Run an ansible playbook and display the results.

        Usage: apb <playbook> [options]

        Available options:
            tags=tag1,tag2,...
            check=no
            subset=*domain1*
        """
        pb = self._get_playbook(msg, playbook)

        for arg in args:
            try:
                key, val = arg.split('=')
            except ValueError:
                raise CommandError('Invalid option: **%s**' % arg)
            else:
                key, val = key.strip(), val.strip()

            if key == 'tags':
                pb.only_tags = map(str.strip, val.split(','))
            elif key == 'check':
                pb.check = _bool(val)
            elif key == 'subset':
                pb.inventory.subset(val)
            else:
                raise CommandError('Invalid option: **%s**' % arg)

        res = []

        try:
            pb.run()
            pb.callbacks.display.flush()
            hosts = sorted(pb.stats.processed.keys())
            res.append(banner(''))

            for h in hosts:
                t = pb.stats.summarize(h)
                res.append('%s : ok=%-4s changed=%-4s unreachable=%-4s failed=%-4s' % (
                    hostcolor(h, t), t['ok'], t['changed'], t['unreachable'], t['failures']
                ))

            res.append('')
        except AnsibleError as exc:
            raise CommandError('Ansible error: **%s**' % exc)

        return '\n'.join(res)

    @command
    def apb_tags(self, msg, playbook):
        """
        List all tags available in a playbook.

        Usage: apb-tags <playbook>
        """
        pb = self._get_playbook(msg, playbook)
        i = 0
        res = ['', 'playbook: %s' % pb.filename, '']

        for play in self._get_playbook_data(pb):
            i += 1
            res.append('  play #%d (%s):\tTAGS: [%s]' % (i, play.name, ','.join(sorted(set(play.tags)))))
            tags = set()

            for task in pb.tasks_to_run_in_play(play):
                tags.update(task.tags)

            res.append('    TASK TAGS: [%s]' % (', '.join(sorted(tags.difference(['untagged'])))))
            res.append('')

        return '\n'.join(res)

    @command
    def apb_tasks(self, msg, playbook):
        """
        List all tasks available in a playbook.

        Usage: apb-tasks <playbook>
        """
        pb = self._get_playbook(msg, playbook)
        i = 0
        res = ['', 'playbook: %s' % pb.filename, '']

        for play in self._get_playbook_data(pb):
            i += 1
            res.append('  play #%d (%s):\tTAGS: [%s]' % (i, play.name, ','.join(sorted(set(play.tags)))))

            for task in pb.tasks_to_run_in_play(play):
                if getattr(task, 'name', None) is not None:  # meta tasks have no names
                    tags = sorted(set(task.tags).difference(['untagged']))
                    res.append('    %s\tTAGS: [%s]' % (task.name, ', '.join(tags)))

            res.append('')

        return '\n'.join(res)

    @command
    def apb_hosts(self, msg, playbook):
        """
        List all hosts available in a playbook.

        Usage: apb-hosts <playbook>
        """
        pb = self._get_playbook(msg, playbook)
        i = 0
        res = ['', 'playbook: %s' % pb.filename, '']

        for play in self._get_playbook_data(pb):
            i += 1
            hosts = pb.inventory.list_hosts(play.hosts)
            res.append('  play #%d (%s): host count=%d' % (i, play.name, len(hosts)))

            for host in hosts:
                res.append('    %s' % host)

            res.append('')

        return '\n'.join(res)
