
# Features

1. ZeroConf / LAN Auto-Discovery (pyknic discovery)

Allows the server to advertise itself on the local network (via mDNS, SSDP, or HMAC-signed UDP broadcast) and enables the bellboy client to automatically discover instances without manually specifying `--server.lobby-url` (using `bellboy discover`).

2. Persistent Task Queue (Stateful Tasks Store)

Optional SQLite/PostgreSQL backend for persisting the queue, execution statuses, and task results across restarts of the pyknic-server daemon.

3. Real-time streaming output (Streaming RPC via WebSockets / SSE)

For long-running operations (backups, copying, external scripts), stream stdout/stderr, completion percentage, and metrics to Bellboy in real time, rather than waiting for a single final JSON response.


4. Prometheus metrics endpoint (/metrics)

Export of standard metrics: task execution time, queue sizes, IOThrottler throughput, cryptography errors, and the number of active sessions.

5. Webhooks

Configurable notifications (Telegram, Discord, Slack, Generic Webhook) for system events: scheduled task failure, successful backup, unauthorized login attempt.

6. Integration with external secret stores

In bellboy, in addition to shm and keyring, add backends for HashiCorp Vault or system TPM 2.0 / Apple Keychain.

# Security issues

1. Application-level rate limiting (including login/*); exponential backoff after N failures.

2. Timing Attack.

File: pyknic/lib/crypto/htpasswd.py (rows 166–185).

```
def match(self, user_name: str, password: str) -> bool:
    user_name_matched = False
    for entry in self.__entries:
        if entry.user_name() == user_name:
            if entry.match(password):
                return True

    if not user_name_matched:
        # make a pause
        secrets.compare_digest(b'', b'')
    return False
```
Issues:

2.1 Logical error: the `user_name_matched` variable is never set to `True`. The `secrets.compare_digest(b'', b'')` call is executed whenever the password is incorrect or the user is not found.

2.2. Timing Oracle: `secrets.compare_digest(b'', b'')` executes in a fraction of a nanosecond, whereas hash computation using Argon2 or BCrypt takes 50–300 ms. An attacker can use response times to definitively enumerate valid usernames in the system (Username Enumeration).

2.3. Linear search: iterating through the `self.__entries` list causes the response time to depend on the record's position in the file.

2.4 Try to limit digest algorithm to argon2id

3. Invalid "sub" type
`sub` is declared as `Union[str, int]` (models/lobby.py:101), even though RFC 7519 requires a string.

4. Unsafe shared memory access
File: pyknic/lib/bellboy/secret_backend.py (row 154).

Using POSIX shared memory at `/dev/shm/pyknic-secrets` makes stored tokens and public keys accessible to other processes and users on the local machine if permissive access masks (umask) are in effect.

5. Request size limit

No request body size limit → potential DoS via parsing.

6. Dangerous "Default-Allow" model for command validation

File: pyknic/tasks/fastapi/lobby.py (rows 372–378)

```
if policy.allowed_commands and command_request.name not in policy.allowed_commands:
    raise fastapi.HTTPException(status_code=403, detail=...)
```
If the administrator leaves `allowed_commands: []` (the default value in many configurations and tests) and `denied_commands: []`, the condition `if policy.allowed_commands` evaluates to false, and any registered command is permitted for execution.

Recommendation. The principle of least privilege (Default-Deny) requires explicit command authorization (whitelisting). If `allowed_commands` is empty, access to all commands should be blocked (or allowed only via the special wildcard `*`).

7. Revocation / Blacklist (Replay Attacks)

The `logout` and `logout_all` commands (pyknic/lib/integrated_commands/logout*.py) remove the token only on the client side. On the server, the token remains fully valid until its time-to-live (TTL) expires (defaulting to 1800 seconds). If a token is compromised, it is impossible to terminate the session without changing the server's master key.

The `jti` (JWT ID) field is generated using `uuid.uuid4()`, but the server does not cache it or verify its uniqueness. An intercepted token can be replayed multiple times until the `exp` time is reached.

8. Log Injection

Logging is performed by concatenating user data without escaping:

```
Logger.info(f'User "{jwt_payload.sub}" authenticated for lobby command with "{jwt_payload.policy_name}" policy')
```

If `sub` contains newline characters (\r\n), an attacker can forge server log entries.

9. [Potential issue] Critical error calling the command handler (exec)

File: pyknic/tasks/fastapi/lobby.py (row 384).

```
command_handler = self.__lobby_registry.get(command_request.name)
command_args_class = command_handler.command_model()
command_args = command_args_class.model_validate(command_request.args)

command_result = await command_handler.exec(command_args)
```

The `command_handler` class is retrieved from the registry (it is a class, not an instance). The `exec(self)` method in the `LobbyCommandHandler` protocol is an instance method that takes no arguments (`self._args` is populated in `prepare_command`). Calling `command_handler.exec(command_args)` passes the validated `command_args` model instead of `self`. If the command attempts to access `self._args`, an `AttributeError` will occur. The call should be made via the factory:
`command_handler.prepare_command(command_args).exec()`.

10. [Potential issue] Sensitive information leakage

(LobbyApp.lobby_command:)

```
except LobbyCommandError as e:
    raise fastapi.HTTPException(status_code=400, detail=str(e))
```

The text of the internal exception is passed to the client without filtering. This may expose system paths, module names, environment details, or internal database or OS errors.

11. [Potenial issue] Incorrect policy selection during authentication

File: pyknic/tasks/fastapi/lobby.py (rows 248–267).

```
for policy in suitable_policies:
    user_id = await policy.authentication_handler.authenticate(request)
    if user_id is not None:
        return self.__generate_auth_token(user_id, policy.policy_name)
```

The `__login` method searches for suitable policies based solely on a match with `fastapi_handler()` and applies the first one it encounters. If multiple policies with the same provider type are configured (e.g., two `bearer_static_token` or `htpasswd` policies with different access rights), the token will always be issued with the permissions of the policy found first in the dictionary. This breaks the separation of access rights between different static tokens or user groups.

12. [Potenial issue] FastAPI dependency type mismatch

File: pyknic/tasks/fastapi/lobby.py (rows 288–290).

The method signature specifies:
auth: typing.Annotated[HTTPAuthorizationCredentials, fastapi.Depends(HTTPBasic())]
The fastapi.security.HTTPBasic() dependency returns an HTTPBasicCredentials object (with .username and .password fields), not HTTPAuthorizationCredentials. Furthermore, the auth argument itself is ignored within __login, and the request is re-parsed inside _BaseHTPasswdProvider.authenticate.

13. [Potenial issue] Removed policy may lead to 500

Files:
- pyknic/lib/fastapi/models/lobby.py (row 109)
- pyknic/tasks/fastapi/lobby.py (rows 355, 362).

Denial of Service (DoS / 500 Error): If a policy is deleted or renamed in the server configuration, a request with a valid token will trigger a `KeyError` at the line `self.__aaa_policies[jwt_payload.policy_name]`, resulting in an unhandled 500 Internal Server Error.

14. [Potential issue] Disabling client-side Audience validation

File: pyknic/lib/bellboy/app.py (row 255).

```
options={"verify_aud": False}
```

The client disables the token audience check, which—given the presence of multiple services in the infrastructure—could allow a token from a different service to be used.

15. [Potential issue] No RBAC

Ignoring roles and groups: The FastAPIIdentity structure contains a `groups` field, but it is discarded when the token is issued. Authorization does not take user groups or roles into account.

# CI/CD

1. Migrate concourse-ci/* and docker/* to pyknic-build code

As an example -- pyknic-todo project

# AI

1. Ask for a code review
