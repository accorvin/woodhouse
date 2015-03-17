woodhouse
==========

Utility to build GitHub pull requests in Jenkins

## Prerequisites

This project uses a fork of Pygithub3 to connect to the GitHub Enterprise API. The fork can be found at https://github.com/accorvin/python-github3
To install Pygithub3, run the following command:

```
sudo pip install git+git://github.com/accorvin/python-github3.git
```

This project uses a fork of the jenkins-webapi project to connect to the Jenkins API. The fork can be found at https://github.com/accorvin/jenkins-webapi
To install jenkins-webapi, run the following command:
```
sudo pip install git+git://github.com/accorvin/jenkins-webapi.git
```

This project also requires PyYaml, which can be installed by running:
```
sudo pip install pyyaml
```

## Configuration

Configuration for Woodhouse is read from the woohouse.conf file. The following values should be set in that file:

* The github api url (the default is the Rackspace enterprise github api)
* The login credentials of a github user with access to the repos you want to monitor
* a comma delineated list of orgs/users whose repos you want to monitor
* For each org/user, a comma delineated list of repos to test
* For each repo being monitored, the name of the corresponding jenkins job
* The url of the jenkins server (the defualt value if the routing team's jenkins server)
* Login credentials to the jenkins server


## Running Woodhouse

Woodhouse was built with the intention of being run every minute as a cron job, however it does not need to be. Simply running the following command will work:
```
python woodhouse.py
```

## Usage

When running, woodhouse will automatically build the jenkins job for any
new pull request. Additionally, every time a change is pushed to the pull
request, the pull request will be built again.

Builds can manually be started by commenting on the pull request. Comments
must contain the words "go" and "woodhouse", in that order. Case doesn't
matter, nor does punctuation.

Similarly, builds can be manually stopped by commenting "stop woodhouse".
Again, case and punctation don't matter.
