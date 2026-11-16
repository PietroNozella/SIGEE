# Textos vigentes na transição dos templates para o banco.
DOCUMENTOS_INICIAIS = {'termos': ('2.0',
            (2026, 9, 21),
            [{'titulo': '1. Sobre o SIGEE',
              'blocos': [{'texto': 'O Sistema Integrado de Gestão de Equipamentos Escolares (SIGEE) é uma '
                                   'plataforma web destinada a apoiar instituições de ensino na organização, no '
                                   'controle e na rastreabilidade de seus equipamentos.'},
                         {'texto': 'Estes Termos regulam o uso do sistema e devem ser observados em conjunto com '
                                   'a Política de Privacidade e com as normas internas da instituição responsável '
                                   'pela conta.'}]},
             {'titulo': '2. Acesso ao sistema',
              'blocos': [{'texto': 'O cadastro não é público. As contas são criadas de forma controlada e recebem '
                                   'um dos perfis funcionais previstos: Administrador, Operador ou Professor. '
                                   'Cada usuário deve utilizar somente a conta que lhe foi atribuída e manter sua '
                                   'senha em sigilo.'},
                         {'texto': 'O escopo atual destina as contas a profissionais autorizados e não prevê '
                                   'contas para alunos, crianças ou adolescentes. Qualquer ampliação desse '
                                   'público exige avaliação específica e atualização destes Termos.'}]},
             {'titulo': '3. Uso permitido',
              'blocos': [{'texto': 'O usuário deve utilizar o SIGEE exclusivamente para as finalidades '
                                   'institucionais autorizadas, respeitando as permissões do seu perfil, a '
                                   'legislação aplicável e as orientações da instituição. As informações '
                                   'cadastradas devem ser verdadeiras, pertinentes e limitadas ao necessário para '
                                   'a gestão dos equipamentos.'}]},
             {'titulo': '4. Condutas não permitidas',
              'blocos': [{'itens': ['compartilhar credenciais ou tentar utilizar a conta de outra pessoa;',
                                    'tentar acessar funções, registros ou áreas sem autorização;',
                                    'inserir dados pessoais excessivos, dados sensíveis sem necessidade '
                                    'autorizada ou conteúdo ilícito;',
                                    'interferir no funcionamento, na segurança ou na integridade do sistema;',
                                    'explorar vulnerabilidades, contornar controles de acesso ou utilizar o '
                                    'sistema para finalidade ilícita.']}]},
             {'titulo': '5. Conteúdo e propriedade intelectual',
              'blocos': [{'texto': 'O usuário permanece responsável pela pertinência e licitude das informações '
                                   'que inserir e deve evitar dados pessoais excessivos em descrições e '
                                   'observações. O software, a identidade visual e os materiais do SIGEE '
                                   'permanecem sujeitos aos direitos de seus respectivos titulares e às licenças '
                                   'aplicáveis.'}]},
             {'titulo': '6. Registros e auditoria',
              'blocos': [{'texto': 'Para proteger o ambiente e assegurar a rastreabilidade, o SIGEE registra '
                                   'eventos de autenticação, acessos negados, ações relevantes e o aceite destes '
                                   'documentos. Esses registros podem ser utilizados para segurança, suporte, '
                                   'apuração de incidentes, cumprimento de obrigações e exercício regular de '
                                   'direitos.'}]},
             {'titulo': '7. Disponibilidade, suporte e encerramento',
              'blocos': [{'texto': 'O SIGEE pode passar por atualizações, manutenções programadas ou interrupções '
                                   'necessárias à segurança e à continuidade do serviço. A instituição e os '
                                   'usuários são responsáveis pela qualidade e pela licitude dos dados inseridos, '
                                   'bem como pelo uso do sistema de acordo com suas atribuições.'},
                         {'texto': 'A conta pode ser inativada quando o vínculo institucional terminar, houver '
                                   'solicitação cabível do titular ou ocorrer uso incompatível com estes Termos. '
                                   'A preservação ou anonimização dos registros relacionados seguirá o Plano de '
                                   'Retenção e Descarte.'}]},
             {'titulo': '8. Uso indevido',
              'blocos': [{'texto': 'O uso indevido pode resultar em bloqueio temporário, inativação da conta, '
                                   'preservação de evidências e comunicação à instituição responsável, sempre de '
                                   'forma proporcional e sem excluir os direitos assegurados pela legislação.'}]},
             {'titulo': '9. Aceite e atualização',
              'blocos': [{'texto': 'O acesso às áreas internas depende do aceite da versão vigente destes Termos '
                                   'e da confirmação de leitura da Política de Privacidade. O sistema registra o '
                                   'usuário, as versões aceitas e a data e hora. Quando uma das versões for '
                                   'alterada, um novo aceite será solicitado.'}]},
             {'titulo': '10. Legislação e contato',
              'blocos': [{'texto': 'Estes Termos são interpretados de acordo com a legislação brasileira e não '
                                   'afastam direitos legalmente assegurados. Dúvidas podem ser encaminhadas para '
                                   '[[contato]].'}]}]),
 'privacidade': ('2.2',
                 (2026, 11, 10),
                 [{'titulo': 'Responsabilidades no tratamento',
                   'blocos': [{'texto': 'A instituição que adota o SIGEE e determina as finalidades e os meios de '
                                        'utilização dos dados atua como controladora. Antes de utilizar dados '
                                        'reais, ela deve ser identificada e aprovar as hipóteses legais, os '
                                        'prazos de retenção, os fornecedores e o canal de atendimento.'},
                              {'texto': 'Enquanto protótipo acadêmico, o SIGEE deve operar somente com dados '
                                        'sintéticos e contas autorizadas da equipe. Esta versão não substitui a '
                                        'validação institucional ou jurídica necessária para uma implantação '
                                        'real.'}]},
                  {'titulo': '1. Dados tratados',
                   'blocos': [{'texto': 'O SIGEE utiliza nome, sobrenome, e-mail, nome de usuário, perfil de '
                                        'acesso, estado da conta, datas técnicas e senha protegida por hash. A '
                                        'senha em texto puro não é armazenada.'},
                              {'texto': 'Reservas relacionam o Professor ao tipo e às unidades de equipamento, '
                                        'local, período, quantidade, estado da solicitação e planejamento '
                                        'pedagógico, com turma, disciplina, atividade e observação opcional. '
                                        'Movimentações podem relacionar Operador, destinatário, equipamento, '
                                        'data, hora e observação.'},
                              {'texto': 'As utilizações pedagógicas relacionam o Professor, a retirada, a turma, '
                                        'a disciplina, a atividade, a observação e a data de registro. As '
                                        'manutenções registram o equipamento, a devolução de origem quando '
                                        'aplicável, os responsáveis pela abertura, início e conclusão, as datas, '
                                        'o estado, o resultado e as descrições da intervenção.'},
                              {'texto': 'A auditoria registra conta, ação, resultado, data, hora, entidade e '
                                        'identificador afetado. A proteção contra tentativas abusivas registra '
                                        'temporariamente nome de usuário, horário, caminho acessado e metadados '
                                        'técnicos do navegador, com senha mascarada e sem armazenar o endereço IP '
                                        'na aplicação.'},
                              {'texto': 'O aceite dos documentos guarda a conta, as versões e a data e hora. '
                                        'Cookies técnicos mantêm a sessão e a proteção CSRF. O envio de '
                                        'recuperação de senha utiliza o endereço de e-mail, o nome exibido e um '
                                        'link temporário.'},
                              {'texto': 'Campos de descrição e observação não devem receber dados pessoais '
                                        'excessivos ou dados sensíveis. O escopo atual não prevê contas ou dados '
                                        'pessoais de alunos, crianças ou adolescentes.'}]},
                  {'titulo': '2. Finalidades',
                   'blocos': [{'itens': ['autenticar usuários e manter a sessão;',
                                         'aplicar permissões conforme o perfil funcional;',
                                         'criar reservas e viabilizar a gestão e a rastreabilidade de '
                                         'equipamentos;',
                                         'planejar o contexto pedagógico das reservas, registrar os usos '
                                         'realizados e consolidar indicadores por turma, disciplina e atividade;',
                                         'acompanhar manutenções e preservar a rastreabilidade das intervenções e '
                                         'de seus responsáveis;',
                                         'registrar eventos de segurança e ações relevantes;',
                                         'comprovar o aceite das versões vigentes dos documentos legais;',
                                         'prestar suporte, prevenir incidentes e manter a segurança do serviço.']},
                              {'texto': 'As hipóteses legais aplicáveis dependem da instituição controladora e '
                                        'estão registradas como propostas na documentação de governança. O aceite '
                                        'destes documentos não é utilizado como consentimento genérico para as '
                                        'funcionalidades obrigatórias.'}]},
                  {'titulo': '3. Compartilhamento e serviços externos',
                   'blocos': [{'itens': ['Vercel: hospedagem da aplicação e processamento de requisições e '
                                         'metadados técnicos;',
                                         'Supabase: hospedagem do banco PostgreSQL e dos dados persistidos pela '
                                         'aplicação;',
                                         'Serviço de e-mail configurado: quando habilitado, o envio por SMTP '
                                         'utiliza destinatário, nome exibido e link temporário de recuperação. O '
                                         'provedor depende da configuração do ambiente; Gmail é um exemplo de '
                                         'configuração, e o fornecedor efetivamente adotado deve ser confirmado '
                                         'pela instituição;',
                                         'BrasilAPI: recebe somente o ano consultado e um identificador técnico '
                                         'do cliente para retornar feriados nacionais.']},
                              {'texto': 'Bootstrap e fontes são servidos pelo próprio SIGEE, sem requisição do '
                                        'navegador a provedores de CDN. A localização do tratamento, eventual '
                                        'transferência internacional e as salvaguardas de cada fornecedor devem '
                                        'ser confirmadas pela controladora antes do uso institucional.'}]},
                  {'titulo': '4. Cookies necessários',
                   'blocos': [{'texto': 'O SIGEE utiliza somente cookies técnicos do Django: o cookie de sessão '
                                        'mantém a autenticação e o cookie CSRF protege formulários contra '
                                        'requisições forjadas. Na configuração atual, a sessão termina após 30 '
                                        'minutos sem navegação ou envio de formulários, ou ao completar 8 horas '
                                        'desde o login, mesmo com atividade. Consultas automáticas de '
                                        'disponibilidade, feriados e estado da sessão não renovam esses prazos. '
                                        'Os limites são configuráveis pela manutenção técnica. O cookie CSRF '
                                        'permanece por até um ano. Esses cookies não são utilizados para '
                                        'publicidade, análise comportamental ou personalização comercial.'}]},
                  {'titulo': '5. Conservação e descarte',
                   'blocos': [{'texto': 'Os critérios por categoria estão descritos no Plano de Retenção e '
                                        'Descarte. Prazos que dependem da instituição permanecem identificados '
                                        'como propostas e devem ser aprovados antes do uso de dados reais.'},
                              {'texto': 'Quando a eliminação direta comprometer um histórico que precise ser '
                                        'preservado, a conta poderá ser inativada e anonimizada. Sessões '
                                        'expiradas e registros temporários de tentativas de autenticação possuem '
                                        'procedimentos específicos de limpeza.'}]},
                  {'titulo': '6. Direitos dos titulares',
                   'blocos': [{'texto': 'O titular pode solicitar confirmação do tratamento, acesso, correção, '
                                        'informação sobre compartilhamentos e, quando aplicável, anonimização, '
                                        'bloqueio, eliminação, portabilidade, oposição e revogação de '
                                        'consentimento específico. O SIGEE não toma decisões que produzam efeitos '
                                        'sobre o usuário unicamente por tratamento automatizado.'},
                              {'texto': 'As solicitações devem ser encaminhadas à instituição responsável pela '
                                        'conta ou para [[contato]]. O atendimento exige verificação de '
                                        'identidade, registro do pedido, análise das restrições aplicáveis e '
                                        'comunicação da decisão.'}]},
                  {'titulo': '7. Segurança e incidentes',
                   'blocos': [{'texto': 'O SIGEE utiliza hash de senhas, sessões, HTTPS, proteção CSRF, validação '
                                        'no servidor, grupos, permissões, limitação temporária de tentativas de '
                                        'login e registros de auditoria. Nenhum sistema é totalmente isento de '
                                        'incidentes.'},
                              {'texto': 'Ocorrências devem seguir o Plano de Resposta a Incidentes: confirmação, '
                                        'contenção, preservação de evidências, identificação dos dados e '
                                        'titulares afetados, avaliação de risco, comunicações necessárias e '
                                        'correção da causa.'}]},
                  {'titulo': '8. Aceite dos documentos',
                   'blocos': [{'texto': 'Ao prosseguir, o usuário aceita os Termos de Uso e declara que leu esta '
                                        'Política. O registro contém a conta, a versão de cada documento e a data '
                                        'e hora. Essa confirmação comprova a apresentação dos documentos e não '
                                        'autoriza finalidades diferentes das informadas.'}]},
                  {'titulo': '9. Alterações desta Política',
                   'blocos': [{'texto': 'Alterações relevantes produzem nova versão e data de vigência. O usuário '
                                        'autenticado deverá confirmar novamente a leitura antes de continuar '
                                        'usando as áreas internas.'}]}])}
