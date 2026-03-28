
To setup main multibranch pipeline:

$ fly -t <name> set-pipeline -n -p pyknic-multibranch-test -c concourse-ci/pyknic-multibranch-test.yml

To setup pipelines for pull request routine:

$ fly -t <name> set-pipeline -n -p pyknic-pull-requests --var github-access-token=<token> --var tg_bot_token=<token> \
  --var tg_chat=<chat> -c concourse-ci/pyknic-pull-requests.yml -l concourse-ci/python-versions.yml

For regular cleanup check:
$ fly -t <name> builds

and:
$ fly -t <name> pipelines --include-archived
