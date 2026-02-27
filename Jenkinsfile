pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  parameters {
    string(name: 'DOCKERHUB_USER', defaultValue: 'sungjin9288', description: 'Docker Hub username')
    string(name: 'IMAGE_TAG', defaultValue: 'jenkins-${BUILD_NUMBER}', description: 'Docker image tag')
    booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Push image to Docker Hub')
  }

  environment {
    BE_IMAGE = "${params.DOCKERHUB_USER}/community-backend:${params.IMAGE_TAG}"
    APP_LOG_FILE = '/tmp/community-backend-jenkins.log'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Install Dependencies') {
      steps {
        sh '''
          set -euo pipefail
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest
        '''
      }
    }

    stage('Unit Test') {
      steps {
        sh '''
          set -euo pipefail
          . .venv/bin/activate
          pytest -q
        '''
      }
    }

    stage('Build Docker Image') {
      steps {
        sh 'docker build -t "$BE_IMAGE" .'
      }
    }

    stage('Push Docker Image') {
      when {
        expression { return params.PUSH_IMAGE }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', usernameVariable: 'DOCKERHUB_USER', passwordVariable: 'DOCKERHUB_PAT')]) {
          sh '''
            set -euo pipefail
            echo "$DOCKERHUB_PAT" | docker login -u "$DOCKERHUB_USER" --password-stdin
            docker push "$BE_IMAGE"
          '''
        }
      }
    }
  }
}
