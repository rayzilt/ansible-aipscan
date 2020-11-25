# ansible-aipscan

Ansible role for deploying [AIPScan](https://github.com/artefactual-labs/AIPScan)

- It requires Artefactual's Nginx and Rabbit MQ roles, based on the excelent work from [@geerlingguy](https://github.com/geerlingguy). Add this to your requirements.yml file:


```
- src: "https://github.com/artefactual-labs/ansible-role-rabbitmq"
  branch: "master"
  name: artefactual.rabbitmq
  
- src: "https://github.com/artefactual-labs/ansible-nginx"
  branch: "master"
  name: "artefactual.nginx"

- src: "https://github.com/artefactual-labs/ansible-aipscan"
  branch: "main"
  name: "artefactual.aipscan"

```

- Sample playbook, intended to be used against an already installed Archivematica instance:

```
- hosts: all
  become: true
  vars:
    aipscan_http_user: "aipscan"
    aipscan_http_password: "artefactual"
  roles:
    - artefactual.nginx
    - artefactual.rabbitmq
    - artefactual.aipscan
```

Aipscan will be available at  port 8057, with user "aipscan" and password "artefactual".


Default variables:
```
aipscan_install_dir: "/usr/share/archivematica/AIPscan"
aipscan_virtualenv: "/usr/share/archivematica/virtualenvs/AIPscan"
aipscan_branch: "main"
aipscan_user: "archivematica"
aipscan_group: "archivematica"
aipscan_listen_port: "8057"
aipscan_http_user: "aipscan"
aipscan_http_password: "artefactual"
```
