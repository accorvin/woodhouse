import hashlib
import random

from jenkins import Build
from jenkins import Jenkins


class JenkinsConnector:
    def __init__(self, jenkins_url, jenkins_user, jenkins_password):
        self.jenkins = Jenkins(jenkins_url, jenkins_user, jenkins_password)

    def generate_job_id(self, repo, pr_num):
        id_string = '{0}{1}{2}'.format(repo, pr_num, random.randint(1, 100000))
        d = hashlib.md5()
        d.update(id_string)
        return d.hexdigest()

    def get_build_from_id(self, job_name, job_id):
        builds = self.jenkins.job(job_name).info(depth=1)['builds']
        for build in builds:
            try:
                parameters = build['actions'][0]['parameters']
                for parameter in parameters:
                    if parameter['name'] == 'id':
                        if parameter['value'] == job_id:
                            return build
            except:
                pass
        return None

    def is_build_queued(self, job_id):
        queue = self.jenkins.queue['items']
        for build in queue:
            try:
                parameters = build['actions'][0]['parameters']
                for param in parameters:
                    if param['name'] == 'id':
                        if param['value'] == job_id:
                            return True
            except:
                return False
        return False

    def get_build_result(self, job_name, job_id):
        build = self.get_build_from_id(job_name, job_id)

        if not build:
            if self.is_build_queued(job_id):
                return 'QUEUED'
            else:
                return 'ERROR'
        if build['building']:
            return 'PENDING'
        else:
            return build['result']

    def get_job_url(self, job_name):
        return self.jenkins.job(job_name).url()

    def get_build_url(self, job_name, job_id):
        if self.is_build_queued(job_id):
            return self.get_job_url(job_name)
        else:
            build = self.get_build_from_id(job_name, job_id)
            if not build:
                return self.get_job_url(job_name)
            else:
                return build['url']

    def start_build(self, job_name, branch, repo, pr_num):
        job_id = self.generate_job_id(repo, pr_num)
        data = {'id': job_id, 'branch': branch}
        self.jenkins.job(job_name).build(data)
        return job_id

    def stop_build(self, job_name, job_id):
        build = self.get_build_from_id(job_name, job_id)
        build_number = build['number']
        job = self.jenkins.job(job_name)
        build_object = Build(job, build_number)
        build_object.stop()

# vim: ai et sts=4 ts=4 sw=4
