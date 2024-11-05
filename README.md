# ansible-aipscan

Ansible role for deploying [AIPScan](https://github.com/artefactual-labs/AIPScan)

- Sample playbook, intended to be used against an already installed Archivematica instance:

```
- hosts: all
  become: true
  vars:
    aipscan_http_user: "aipscan"
    aipscan_http_password: "artefactual"
  roles:
    - role: "artefactual.nginx"
      become: "yes"
      vars:
        nginx_sites:
          aipscan:
            - listen 8057
            - client_max_body_size 256M
            - satisfy any;
              auth_basic "Restricted";
              auth_basic_user_file /etc/nginx/auth_basic/aipscan
            - location / {
                proxy_pass http://127.0.0.1:4573;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              }
        nginx_auth_basic_files:
          aipscan:
            - "{{ aipscan_http_user }}:{{ aipscan_http_password | default('pass') | string | password_hash('md5_crypt') }}"
      tags:
        - "nginx"

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
```
