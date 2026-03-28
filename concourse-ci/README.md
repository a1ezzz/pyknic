
To setup main multibranch pipeline:

$ fly -t <name> set-pipeline -n -p pyknic-multibranch-test --var tg_bot_token==<token> --var tg_chat=<chat> \
  -l concourse-ci/python-versions.yml -c concourse-ci/pyknic-multibranch-test.yml

To setup pipelines for pull request routine:

$ fly -t <name> set-pipeline -n -p pyknic-pull-requests --var github-access-token=<token> --var tg_bot_token=<token> \
  --var tg_chat=<chat> -l concourse-ci/python-versions.yml -c concourse-ci/pyknic-pull-requests.yml

For regular cleanup check:
$ fly -t <name> builds

and:
$ fly -t <name> pipelines --include-archived
