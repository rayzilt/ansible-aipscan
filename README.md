# ansible-aipscan

Ansible role for deploying [AIPScan].

> [!IMPORTANT]
> For legacy deployments targeting AIPscan v0.7.0 or older, use the [legacy-0.7]
  tag of this role.

It requires Artefactual's Nginx and Rabbit MQ roles - add this to your
`requirements.yml` file:

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

Sample playbook, intended to be used against an already installed Archivematica
instance:

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

AIPscan will be available at port 8057, with user `"aipscan"` and password
`"artefactual"`.

[AIPscan]: https://github.com/artefactual-labs/AIPScan
[legacy-0.7]: https://github.com/artefactual-labs/ansible-aipscan/releases/tag/legacy-0.7
