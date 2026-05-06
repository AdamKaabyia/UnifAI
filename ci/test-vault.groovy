properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "GENIE-948_hashicorp_integration", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "GENIE-948_hashicorp_integration", description: "Git branch to build images from."),
        
        // 🔒 Vault Parameters
        string(name: 'VAULT_SECRET_PATH', defaultValue: 'apps/automation-and-tools/unifai', description: 'Vault secret path'),
        string(name: 'VAULT_SECRET_KEY', defaultValue: 'redis_port', description: 'Key within the secret')
    ])
])


def secret_lists = [
    redis: ['redis_password', 'redis_port', 'redis_insight_port'],
    rmq: ['rmq_username', 'rmq_password'],
    hf: ['HF_TOKEN'],
    secret_key: ['secret_key'],
    umami: ['umami_app_secret', 'umami_password'],
    keycloak: ['keycloak_base_url', 'client_id', 'client_secret', 'keycloak_realm'],
    multiagent: ['CREDENTIAL_ENCRYPTION_KEY', 'MCP_AUTH_STATE_SECRET'],
    rag: ['default_slack_bot_token', 'default_slack_user_token'],
]


pipeline {
    agent any

    stages {
    //     stage('Read Secret key from Vault natively') {
    //         steps {
    //             withVault(
    //                 configuration: [
    //                     vaultUrl: '',           // leave empty to use global config
    //                     vaultCredentialId: ''   // leave empty to use global config
    //                 ],
    //                 vaultSecrets: [
    //                     [
    //                         path: "${params.VAULT_SECRET_PATH}",
    //                         secretValues: [
    //                             [envVar: 'MY_SECRET', vaultKey: "${params.VAULT_SECRET_KEY}"]
    //                         ]
    //                     ]
    //                 ]
    //             ) {
    //                 sh 'echo "Secret retrieved (masked): $MY_SECRET"'
    //                 // Use MY_SECRET env var in your steps here
    //             }
    //         }
    //     }
        stage('Read Secret key permodule') {
            steps {
                script {
                    secret_lists.each { module, secrets ->
                        withVault(
                            configuration: [
                                vaultUrl: '',           // leave empty to use global config
                                vaultCredentialId: ''   // leave empty to use global config
                            ],
                            vaultSecrets: [
                                [path: "${params.VAULT_SECRET_PATH}/${module}",
                                secretValues: secrets.collect { secret_key -> [envVar: "${secret_key}", vaultKey: secret_key] }]
                            ]
                        ) {
                            secrets.each { secret ->
                                sh "echo 'Secret retrieved (masked): \$${secret}'"
                            }
                        }
                    }
                }

            }
        } 
    }  
}