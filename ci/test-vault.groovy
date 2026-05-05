properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "GENIE-948_hashicorp_integration", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "GENIE-948_hashicorp_integration", description: "Git branch to build images from."),
        
        // 🔒 Vault Parameters
        string(name: 'VAULT_SECRET_PATH', defaultValue: 'apps/automation-and-tools/unifai/redis', description: 'Vault secret path'),
        string(name: 'VAULT_SECRET_KEY', defaultValue: 'redis_port', description: 'Key within the secret')
    ])
])

pipeline {
    agent any

    stages {
        stage('Read Secret key from Vault natively') {
            steps {
                withVault(
                    configuration: [
                        vaultUrl: '',           // leave empty to use global config
                        vaultCredentialId: ''   // leave empty to use global config
                    ],
                    vaultSecrets: [
                        [
                            path: "${params.VAULT_SECRET_PATH}",
                            secretValues: [
                                [envVar: 'MY_SECRET', vaultKey: "${params.VAULT_SECRET_KEY}"]
                            ]
                        ]
                    ]
                ) {
                    sh 'echo "Secret retrieved (masked): $MY_SECRET"'
                    // Use MY_SECRET env var in your steps here
                }
            }
        }
        stage('Read Secret key from Vault using approle') {
            steps {
            withCredentials([
                usernamePassword(
                    credentialsId: 'vault_creds',
                    usernameVariable: 'ROLE_ID',
                    passwordVariable: 'SECRET_ID'
                )
            ]) {
                script {
                    def token = sh(
                        script: '''
                            export VAULT_ADDR='https://vault.corp.redhat.com:8200/'
                            export VAULT_SKIP_VERIFY=true
                            vault write -field=token auth/approle/login \
                                role_id=$ROLE_ID \
                                secret_id=$SECRET_ID
                        ''',
                        returnStdout: true
                    ).trim()
                    def json = sh(
                        script: """
                            export VAULT_ADDR='https://vault.corp.redhat.com:8200/'
                            export VAULT_SKIP_VERIFY=true
                            export VAULT_TOKEN=${token}
                            vault kv get -format=json ${params.VAULT_SECRET_PATH}
                        """,
                        returnStdout: true
                    ).trim()
                    def secrets = readJSON text: json
                    def data = secrets.data.data
                    data.each { key, value -> echo "Key: ${key}" }
                }
            }
        }
        }
    }
}