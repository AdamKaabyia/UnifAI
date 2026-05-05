properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "main", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "main", description: "Git branch to build images from."),
        
        // 🔒 Vault Parameters
        string(name: 'VAULT_SECRET_PATH', defaultValue: 'apps/automation-and-tools/unifai/redis', description: 'Vault secret path'),
        string(name: 'VAULT_SECRET_KEY', defaultValue: 'redis_port', description: 'Key within the secret')
    ])
])

pipeline {
    agent any

    stages {
        stage('Read Secret from Vault') {
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
    }
}