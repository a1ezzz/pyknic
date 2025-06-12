
To setup main multibranch pipeline:

$ fly -t <name> set-pipeline -n -p pyknic-multibranch-test -c concourse-ci/pyknic-multibranch-test.yml

To setup pipelines for pull request routine:

$ fly -t <name> set-pipeline -n -p pyknic-pull-requests --var github-access-token=<token> -c concourse-ci/pyknic-pull-requests.yml

For regular cleanup check:
$ fly -t <name> builds

and:
$ fly -t <name> pipelines --include-archived

