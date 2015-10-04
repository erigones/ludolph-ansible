ludolph-ansible
###############

`Ludolph <https://github.com/erigones/Ludolph>`_: Ansible plugin

Simple plugin for running ansible commands and playbooks.

.. image:: https://badge.fury.io/py/ludolph-ansible.png
    :target: http://badge.fury.io/py/ludolph-ansible


Installation
------------

- Install the latest released version using pip::

    pip install ludolph-ansible

- Add new plugin section into Ludolph configuration file::

    [ludolph_ansible.playbook]
    basedir = /path/to/ansible/base/directory
    playbooks = alias1:playbook1.yml,pb2:playbook2.yml
    private_key_file = /path/private.key

- Reload Ludolph::

    service ludolph reload


**Dependencies:**

- `Ludolph <https://github.com/erigones/Ludolph>`_ (0.7.0+)
- `ansible <http://www.ansible.com/>`_ (>=1.9 && < 2.0)


Links
-----

- Wiki: https://github.com/erigones/Ludolph/wiki/How-to-create-a-plugin#create-3rd-party-plugin
- Bug Tracker: https://github.com/erigones/ludolph-ansible/issues
- Google+ Community: https://plus.google.com/u/0/communities/112192048027134229675
- Twitter: https://twitter.com/erigones


License
-------

For more information see the `LICENSE <https://github.com/erigones/ludolph-ansible/blob/master/LICENSE>`_ file.
