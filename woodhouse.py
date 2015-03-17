#! /usr/bin/env python

import ConfigParser
import json
import os
import re
import sys
import yaml

from pygithub3 import Github

from jenkins_connector import JenkinsConnector


class Woodhouse:
    
    CONFIG_FILE_NAME = 'woodhouse.conf'
    PR_DATA_FILE = 'woodhouse.data'

    def __init__(self):
        self.config = ConfigParser.SafeConfigParser()
        self.get_config()
        self.read_pr_data()

        gh_api = self.config.get('github', 'api_url')

        if self.config.has_option('github', 'token'):
            gh_token = self.config.get('github', 'token')
            self.gh = Github(token=gh_token, base_url=gh_api)
        else:
            gh_login = self.config.get('github', 'login')
            gh_password = self.config.get('github', 'password')
            self.gh = Github(login=gh_login, password=gh_password, base_url=gh_api)

        j_url = self.config.get('jenkins', 'url')
        j_user = self.config.get('jenkins', 'user')
        j_password = self.config.get('jenkins', 'password')
        self.jenkins = JenkinsConnector(j_url, j_user, j_password)

        self.orgs = self.get_orgs()

    def get_orgs(self):
        all_orgs = self.config.get('github', 'orgs').split(',')
        real_orgs = []
        for org in all_orgs:
            if org and org != '':
                real_orgs.append(org)
        return real_orgs

    def clean_old_prs(self):
        for org in self.orgs:
            org_repos = self.get_repo_list(org)
            for repo in org_repos:
                prs_to_delete = []
                pr_nums = self.get_pull_request_numbers(org, repo)
                if self.pr_data.has_key(org):
                    if self.pr_data[org].has_key(repo):
                        for pr in self.pr_data[org][repo]:
                            if pr not in pr_nums:
                                prs_to_delete.append(pr)
                for pr in prs_to_delete:
                    self.pr_data[org][repo].pop(pr)
        self.write_pr_data(self.pr_data)


    def find_new_prs(self):
        for org in self.orgs:
            org_repos = self.get_repo_list(org)
            for repo in org_repos:
                pr_nums = self.get_pull_request_numbers(org, repo)
                for number in pr_nums:
                    pr = self.get_pull_request(org, repo, str(number))
                    requires_testing = self.check_pr_status(pr, repo, org)
                    if requires_testing:
                        self.start_pr_test(repo, pr, org)

    def update_build_statuses(self):
        for org in self.orgs:
            if self.pr_data.has_key(org):
                for repo in self.pr_data[org].keys():
                    repo_job_name = self.get_jenkins_job_name(repo)
                    for pr_num in self.pr_data[org][repo].keys():
                        job_id = self.pr_data[org][repo][pr_num]['job_id']
                        build_status = self.jenkins.get_build_result(repo_job_name,
                                                                     job_id)

                        build_url = self.jenkins.get_build_url(repo_job_name, job_id)

                        if build_status == 'PENDING':
                            self.pr_data[org][repo][pr_num]['status'] = build_status
                            self.write_pr_data(self.pr_data)
                        elif build_status == 'QUEUED':
                            pass
                        elif build_status == 'ERROR':
                            self.delete_build_data(repo, pr_num, org)
                        elif build_status == 'SUCCESS':
                            self.mark_succeeded(org, repo, pr_num, 'SUCCESS',
                                                build_url, repo_job_name, job_id)
                        else:
                            self.mark_failed(org, repo, pr_num, 'FAILURE',
                                             build_url, repo_job_name, job_id)

    def mark_failed(self, org, repo, pr_num, result_string, build_url,
                    repo_job_name, job_id):
        description_1 = 'The Jenkins job for this pull request failed. '
        description_2 = 'For more information, go to: {0}'.format(build_url)
        comment = '{0}{1}'.format(description_1, description_2)
        if self.pr_data[org][repo][pr_num]['status'] != result_string:
            self.mark_result(org, repo, pr_num, result_string, repo_job_name,
                             job_id, description_1)
            self.post_pr_comment(org, repo, pr_num, comment)
    
    def mark_succeeded(self, org, repo, pr_num, result_string, build_url,
                       repo_job_name, job_id):
        description_1 = 'The Jenkins job for this pull request succeeded. '
        description_2 = 'For more information, go to: {0}'.format(build_url)
        comment = '{0}{1}'.format(description_1, description_2)
        if self.pr_data[org][repo][pr_num]['status'] != 'SUCCESS':
            self.mark_result(org, repo, pr_num, result_string, repo_job_name,
                             job_id, description_1)
            self.post_pr_comment(org, repo, pr_num, comment)

    def mark_result(self, org, repo, pr_num, result_string, repo_job_name,
                    job_id, description):
        self.pr_data[org][repo][pr_num]['status'] = result_string
        self.write_pr_data(self.pr_data)
        sha = self.pr_data[org][repo][pr_num]['sha']
        self.post_pr_status(repo, sha, result_string, org, repo_job_name,
                            job_id, description)

    def post_pr_comment(self, org, repo, pr_num, comment):
        self.gh.issues.comments.create(pr_num, comment, user=org, repo=repo)

    def post_pr_status(self, repo, sha, status, org, repo_job_name, job_id,
                       description=None):
        build_url = self.jenkins.get_build_url(repo_job_name, job_id)
        self.gh.statuses.create(repo, sha, status.lower(), org,
                                description=description, target_url=build_url)

    def delete_build_data(self, repo, pr_num, org):
        self.pr_data[org][repo].pop(pr_num, None)
        self.write_pr_data(self.pr_data)

    def get_config(self, config_file_name=CONFIG_FILE_NAME):
        dir_name = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(dir_name, config_file_name)
        self.config.read(config_file)
        
    def get_repo_list(self, org):
        config_line = self.config.get('repos', org)
        repo_list = []
        for repo in config_line.split(','):
            repo_list.append(repo.strip())
        return repo_list

    def get_pull_request_numbers(self, org_name, repo_name):
        pr_numbers = []
        pull_requests = self.gh.pull_requests.list(user=org_name,
                                                    repo=repo_name).all()
        for pr in pull_requests:
            pr_numbers.append(str(pr.number))
        return pr_numbers

    def get_pull_request(self, org_name, repo_name, pr_number):
        return self.gh.pull_requests.get(pr_number, org_name, repo_name)

    def read_pr_data(self, data_file_name=PR_DATA_FILE):
        dir_name = os.path.dirname(os.path.abspath(__file__))
        data_file_path = os.path.join(dir_name, data_file_name)
        if os.path.exists(data_file_path):
            with open(data_file_path) as data_file:
                try:
                    json_data = json.loads(data_file.read())
                except:
                    json_data = {}
                self.pr_data = yaml.load(json.dumps(json_data))
        else:
            self.pr_data = {}

    def check_pr_status(self, pr, repo, org):
        if self.go_comment_exists(pr, repo, org):
            return True

        if self.stop_comment_exists(pr, repo, org):
            pr_num = str(pr.number)
            job_name = self.get_jenkins_job_name(repo)
            job_id = self.pr_data[org][repo][pr_num]['job_id']
            self.jenkins.stop_build(job_name, job_id)
            return False

        if self.pr_data.has_key(org):
            if self.pr_data[org].has_key(repo):
                num = str(pr.number)
                if self.pr_data[org][repo].has_key(num):
                    last_seen_data = self.pr_data[org][repo][num]
                    last_seen_sha = last_seen_data['sha']
                    head_sha = pr.head['sha']
                    if head_sha == last_seen_sha:
                        return False
                    else:
                        return True
                else:
                    return True
            else:
                return True
        else:
            return True

    def delete_comment(self, org, repo, comment_id):
        self.gh.issues.comments.delete(comment_id, org, repo)

    def comment_exists(self, pr_number, repo, org, pattern):
        issue_comments = self.gh.issues.comments.list(pr_number, org, repo).all()
        for comment in issue_comments:
            comment_text = comment.body.lower()
            if pattern.match(comment_text):
                return comment.id
        return False

    def go_comment_exists(self, pull_request, repo, org):
        pattern = re.compile(".*go.*woodhouse.*")
        pr_number = str(pull_request.number)
        building_comment = 'As you wish, sir.'

        comment_id = self.comment_exists(pr_number, repo, org, pattern)
        if comment_id:
                self.delete_comment(org, repo, comment_id)
                self.post_pr_comment(org, repo, pr_number, building_comment)
                return True

        return False

    def stop_comment_exists(self, pull_request, repo, org):
        pattern = re.compile(".*stop.*woodhouse.*")
        stopped_comment = 'The build for this pull request was stopped.'
        pr_number = str(pull_request.number)

        comment_id = self.comment_exists(pr_number, repo, org, pattern)
        if comment_id:
            self.delete_comment(org, repo, comment_id)
            self.post_pr_comment(org, repo, pr_number, stopped_comment)
            self.pr_data[org][repo][pr_number]['status'] = 'STOPPED'
            self.write_pr_data(self.pr_data)
            sha = self.pr_data[org][repo][pr_number]['sha']
            self.post_pr_status(repo, sha, 'error', org)
            return True
        return False

    def mark_pr_building(self, repo, pull_request, repo_job_name, job_id,
                         org):
        pr_num = str(pull_request.number)
        sha = str(pull_request.head['sha'])
        description = 'This pull request is being built in Jenkins'

        data = {
                'sha': sha,
                'job_id': job_id,
                'status': 'PENDING'
               }
        if not self.pr_data.has_key(org):
            self.pr_data[org] = {}
        if not self.pr_data[org].has_key(repo):
            self.pr_data[org][repo] = {}
        if not self.pr_data[org][repo].has_key(pr_num):
            self.pr_data[org][repo][pr_num] = {}

        self.pr_data[org][repo][pr_num] = data
        self.write_pr_data(self.pr_data)
        self.post_pr_status(repo, sha, 'PENDING', org, repo_job_name, job_id,
                            description=description)

    def write_pr_data(self, data, data_file_name=PR_DATA_FILE):
        dir_name = os.path.dirname(os.path.abspath(__file__))
        data_file_path = os.path.join(dir_name, data_file_name)
        with open(data_file_path, 'w') as data_file:
            json.dump(data, data_file, ensure_ascii=True)

    def get_jenkins_job_name(self, repo):
        try:
            job_name = self.config.get('jenkins-jobs', repo)
        except ConfigParser.NoOptionError:
            sys.exit(1)
        return job_name

    def start_pr_test(self, repo, pr, org):
        branch = pr.head['ref']
        pr_num = str(pr.number)
        job_name = self.get_jenkins_job_name(repo)

        try:
            old_job_id = self.pr_data[org][repo][pr_num]['job_id']
            if old_job_id:
                self.jenkins.stop_build(job_name, old_job_id)
        except:
            pass

        job_id = self.jenkins.start_build(job_name, branch, repo, pr_num)
        self.mark_pr_building(repo, pr, job_name, job_id, org)

if __name__ == '__main__':
    woodhouse = Woodhouse()
    woodhouse.update_build_statuses()
    woodhouse.clean_old_prs()
    woodhouse.find_new_prs()

# vim: ai et sts=4 ts=4 sw=4
