# ansible-aipscan

Installs [AIPscan] on Linux hosts using Ansible.

## Compatibility

This role targets AIPscan v0.9.0 and newer.

> [!IMPORTANT]
> For legacy deployments targeting AIPscan v0.8.0 or earlier, use the
  [legacy-0.7] tag of this role. If you are upgrading and need to migrate an
  existing SQLite database, see the [migration notes][sqlite-migration].

## Role variables

Review [`defaults/main.yml`] for the full list of tunable variables. The file
includes inline comments for clarity and self-documentation.

## Dependencies

AIPScan depends on **MySQL** and **RabbitMQ**. In most deployments, **Nginx** is
used as a load balancer and to serve static files, while **Typesense** can
optionally be deployed to improve reporting performance.

The choice of how to deploy and manage these services is left to the system
administrator. See [`molecule/default/requirements.yml`] for the supporting
Ansible roles used in our test pipeline.

## Example playbook

Take a look at [`molecule/default/converge.yml`], which we're using in our
testing pipeline, for a complete example.

Below is a minimal example playbook that installs AIPscan with a single storage
source:

```yaml
- hosts: aipscan_server
  roles:
    - role: artefactual.aipscan
      vars:
        aipscan_secret_key: "secretkeyvalue"
        aipscan_storage_sources:
          - name: "Demo Storage Service"
            url: "http://192.168.1.100:8000"
            username: "demouser"
            api_key: "demoapikey"
```

## Tags

The role exposes the following tags to run a subset of tasks:
- `uv` – install or update the uv packaging tool.
- `install` – create the managed virtual environment and install AIPscan.
- `database` – run Flask database migrations.
- `service` – update configuration and manage systemd units.

## License

This project is licensed under the Apache-2.0 license ([LICENSE] or
<https://opensource.org/licenses/Apache-2.0>).

[AIPscan]: https://github.com/artefactual-labs/AIPScan
[legacy-0.7]: https://github.com/artefactual-labs/ansible-aipscan/releases/tag/legacy-0.7
[sqlite-migration]: https://github.com/artefactual-labs/AIPscan/tree/v0.8.0-beta?tab=readme-ov-file#production-deployments
[LICENSE]: ./LICENSE
[`molecule/default/requirements.yml`]: ./molecule/default/requirements.yml
[`molecule/default/converge.yml`]: ./molecule/default/converge.yml
[`defaults/main.yml`]: ./defaults/main.yml
