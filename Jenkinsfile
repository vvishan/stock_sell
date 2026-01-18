pipeline {
    agent any
    environment {
        ALPACA_API_KEY    = credentials('alpaca-api-key')
        ALPACA_SECRET_KEY = credentials('alpaca-secret-key')
    }

    stages {
        stage('Create Env Build') {
            steps {
                sh '''
                    #!/bin/bash
                    set -e

                    # Step 1: Create virtual environment if it doesn't exist
                    if [ ! -d "venv" ]; then
                    echo "Creating Python virtual environment..."
                    python3 -m venv venv
                    fi
                    echo "Env Build complete."
                '''
            }
        }
        stage('Activating and souce Libraries') {
            steps {
                sh '''
                #!/bin/bash
                echo "Activating virtual environment..."
                . venv/bin/activate

                echo "Upgrading pip..."
                pip install --upgrade pip

                pip install alpaca-py yfinance pandas
                pip install pandas-market-calendars
                '''
            }
        }
        stage('Test') {
            steps {
                sh '''
                #!/bin/bash
                echo "Running tests..."
                python3 -u safetest.py
                # Add test commands here
                '''
            }
        }
    }
}
