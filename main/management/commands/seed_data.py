"""
main/management/commands/seed_data.py
Comando para poblar datos iniciales en la base de datos (métricas y usuario admin)
Ejecutarse automáticamente después de las migraciones
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from main.models import Metric


class Command(BaseCommand):
    help = 'Poblar la base de datos con datos iniciales (métricas y usuario admin)'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando población de datos iniciales...\n')

        # ============================================
        # 1. CREAR USUARIO ADMIN
        # ============================================
        self.stdout.write('Creando usuario admin...')
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@nexscat.local',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        
        if created:
            admin_user.set_password('admin')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('   Usuario admin creado'))
            self.stdout.write('      Usuario: admin')
            self.stdout.write('      Contraseña: admin')
        else:
            self.stdout.write('     Usuario admin ya existe')

        # ============================================
        # 2. CARGAR MÉTRICAS DE SOURCEMETER (99 métricas)
        # ============================================
        self.stdout.write('\n Cargando métricas de SourceMeter...')
        
        sourcemeter_metrics = [
            {'name': 'Comment Lines of Code', 'description': 'Number of comment and documentation code lines.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'CLOC'},
            {'name': 'Lack of Cohesion in Methods 5', 'description': 'Number of functionalities of the class.', 'domain': 'Cohesion metrics', 'tool': 'SourceMeter', 'key': 'LCOM5'},
            {'name': 'Halstead Calculated Program Length', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HCPL'},
            {'name': 'Halstead Difficulty', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HDIF'},
            {'name': 'Halstead Effort', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HEFF'},
            {'name': 'Halstead Number of Delivered Bugs', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HNDB'},
            {'name': 'Halstead Program Length', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HPL'},
            {'name': 'Halstead Program Vocabulary', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HPV'},
            {'name': 'Halstead Time Required to Program', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HTRP'},
            {'name': 'Halstead Volume', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'HVOL'},
            {'name': 'Maintainability Index (Microsoft version)', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'MIMS'},
            {'name': 'Maintainability Index (Original version)', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'MI'},
            {'name': 'Maintainability Index (SEI version)', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'MISEI'},
            {'name': 'Maintainability Index (SourceMeter version)', 'description': '', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'MISM'},
            {'name': "McCabe's Cyclomatic Complexity", 'description': 'Complexity of the method/file expressed as the number of independent control flow paths in it', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'McCC'},
            {'name': 'Nesting Level', 'description': 'Complexity of the method/class expressed as the depth of the maximum embeddedness of its conditional, iteration and exception handling block scopes', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'NL'},
            {'name': 'Nesting Level Else-If', 'description': 'Complexity of the method/class expressed as the depth of the maximum embeddedness of its conditional, iteration and exception handling block scopes.', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'NLE'},
            {'name': 'Weighted Methods per Class', 'description': 'Complexity of the class expressed as the number of independent control flow paths in it.', 'domain': 'Complexity metrics', 'tool': 'SourceMeter', 'key': 'WMC'},
            {'name': 'Coupling Between Object classes', 'description': 'Number of directly used other classes (e.g. by inheritance, function call, type reference, attribute reference).', 'domain': 'Coupling metrics', 'tool': 'SourceMeter', 'key': 'CBO'},
            {'name': 'Coupling Between Object classes Inverse', 'description': 'Number of other classes, which directly use the class.', 'domain': 'Coupling metrics', 'tool': 'SourceMeter', 'key': 'CBOI'},
            {'name': 'Number of Incoming Invocations', 'description': 'Number of other methods and attribute initializations which directly call the method or the local methods of the class.', 'domain': 'Coupling metrics', 'tool': 'SourceMeter', 'key': 'NII'},
            {'name': 'Number of Outgoing Invocations', 'description': 'Number of directly called methods or methods of other classes.', 'domain': 'Coupling metrics', 'tool': 'SourceMeter', 'key': 'NOI'},
            {'name': 'Response set For Class', 'description': 'Number of local (i.e. not inherited) methods in the class (NLM) plus the number of directly invoked other methods by its methods or attribute initializations (NOI).', 'domain': 'Coupling metrics', 'tool': 'SourceMeter', 'key': 'RFC'},
            {'name': 'API Documentation', 'description': 'Ratio of the number of documented public methods in the class +1 if the class itself is documented to the number of all public methods in the class + 1 (the class itself)', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'AD'},
            {'name': 'Comment Density', 'description': 'Ratio of the comment lines of the method/class/package (CLOC) to the sum of its comment (CLOC) and logical lines of code (LLOC).', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'CD'},
            {'name': 'Documentation Lines of Code', 'description': 'Number of documentation code lines of the method/class.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'DLOC'},
            {'name': 'Public Documented API', 'description': 'Number of documented public methods in the class/file/package.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'PDA'},
            {'name': 'Public Undocumented API', 'description': 'Number of undocumented public methods in the class/file/package.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'PUA'},
            {'name': 'Total API Documentation', 'description': 'Nratio of the number of documented public classes and methods in the package/component to the number of all of its public classes and methods, including its subpackages/subcomponents.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'TAD'},
            {'name': 'Total Comment Density', 'description': 'Ratio of the total comment lines of the method/class/package/component (TCLOC) to the sum of its total comment (TCLOC) and total logical lines of code (TLLOC).', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'TCD'},
            {'name': 'Total Comment Lines of Code', 'description': 'Number of comment and documentation code lines of the method/class/package/component.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'TCLOC'},
            {'name': 'Total Public Documented API', 'description': 'Number of documented public classes and methods in the package/component.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'TPDA'},
            {'name': 'Total Public Undocumented API', 'description': 'Number of undocumented public classes and methods in the package/component.', 'domain': 'Documentation metrics', 'tool': 'SourceMeter', 'key': 'TPUA'},
            {'name': 'Depth of Inheritance Tree', 'description': 'Length of the path that leads from the class to its farthest ancestor in the inheritance tree.', 'domain': 'Inheritance metrics', 'tool': 'SourceMeter', 'key': 'DIT'},
            {'name': 'Number of Ancestors', 'description': 'Number of classes, interfaces, enums and annotations from which the class is directly or indirectly inherited.', 'domain': 'Inheritance metrics', 'tool': 'SourceMeter', 'key': 'NOA'},
            {'name': 'Number of Children', 'description': 'Number of classes, interfaces, enums and annotations which are directly derived from the class.', 'domain': 'Inheritance metrics', 'tool': 'SourceMeter', 'key': 'NOC'},
            {'name': 'Number of Descendants', 'description': 'Number of classes, interfaces, enums, annotations, which are directly or indirectly derived from the class.', 'domain': 'Inheritance metrics', 'tool': 'SourceMeter', 'key': 'NOD'},
            {'name': 'Number of Parents', 'description': 'Number of classes, interfaces, enums and annotations from which the class is directly inherited.', 'domain': 'Inheritance metrics', 'tool': 'SourceMeter', 'key': 'NOP'},
            {'name': 'Lines of Code', 'description': 'Number of code lines of the method/class/file/package, including empty and comment lines.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'LOC'},
            {'name': 'Logical Lines of Code', 'description': 'Number of non-empty and non-comment code lines of the method/class/file/package.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'LLOC'},
            {'name': 'Number of Attributes', 'description': 'Number of attributes in the class, including the inherited ones', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NA'},
            {'name': 'Number of Classes', 'description': 'Number of classes in the package.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NCL'},
            {'name': 'Number of Enums', 'description': 'Number of enums in the package.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NEN'},
            {'name': 'Number of Getters', 'description': 'Number of getter methods in the class, including the inherited ones.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NG'},
            {'name': 'Number of Interfaces', 'description': 'Number of interfaces in the package.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NIN'},
            {'name': 'Number of Local Attributes', 'description': 'Number of local (i.e. not inherited) attributes in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLA'},
            {'name': 'Number of Local Getters', 'description': 'Number of local (i.e. not inherited) getter methods in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLG'},
            {'name': 'Number of Local Methods', 'description': 'Number of local (i.e. not inherited) methods in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLM'},
            {'name': 'Number of Local Public Attributes', 'description': 'Number of local (i.e. not inherited) public attributes in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLPA'},
            {'name': 'Number of Local Public Methods', 'description': 'Number of local (i.e. not inherited) public methods in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLPM'},
            {'name': 'Number of Local Setters', 'description': 'Number of local (i.e. not inherited) setter methods in the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NLS'},
            {'name': 'Number of Methods', 'description': 'Number of methods in the class, including the inherited ones.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NM'},
            {'name': 'Number of Packages', 'description': 'Number of directly contained subpackages of the package.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NPKG'},
            {'name': 'Number of Parameters', 'description': 'Number of the parameters of the method. The varargs parameter counts as one.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NUMPAR'},
            {'name': 'Number of Public Attributes', 'description': 'Number of public attributes in the class, including the inherited ones.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NPA'},
            {'name': 'Number of Public Methods', 'description': 'Number of public methods in the class, including the inherited ones.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NPM'},
            {'name': 'Number of Setters', 'description': 'Number of setter methods in the class, including the inherited ones.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NS'},
            {'name': 'Number of Statements', 'description': 'Number of statements in the method/class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'NOS'},
            {'name': 'Total Lines of Code', 'description': 'Number of code lines of the method/class/package/component, including empty and comment lines, as well as its anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TLOC'},
            {'name': 'Total Logical Lines of Code', 'description': 'Number of non-empty and non-comment code lines of the method/class/package/component, including the non-empty and non-comment lines of its anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TLLOC'},
            {'name': 'Total Number of Attributes', 'description': 'Number of attributes in the class, including the inherited ones, as well as the inherited and local attributes of its nested, anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNA'},
            {'name': 'Total Number of Classes', 'description': 'Number of classes in the package, including the classes of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNCL'},
            {'name': 'Total Number of Directories', 'description': 'Number of directories that belong to the package, including the directories of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNDI'},
            {'name': 'Total Number of Enums', 'description': 'Number of enums in the package, including the enums of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNEN'},
            {'name': 'Total Number of Files', 'description': 'Number of files that belong to the package, including the files of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNFI'},
            {'name': 'Total Number of Getters', 'description': 'Number of getter methods in the class, including the inherited ones, as well as the inherited and local getter methods of its nested, anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNG'},
            {'name': 'Total Number of Interfaces', 'description': 'Number of interfaces in the package, including the interfaces of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNIN'},
            {'name': 'Total Number of Local Attributes', 'description': 'Number of local (i.e. not inherited) getter methods in the class, including the local getter methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLA'},
            {'name': 'Total Number of Local Getters', 'description': 'Number of local (i.e. not inherited) methods in the class, including the local methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLG'},
            {'name': 'Total Number of Local Methods', 'description': 'Number of functionalities of the class.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLM'},
            {'name': 'Total Number of Local Public Attributes', 'description': 'Number of local (i.e. not inherited) public attributes in the class, including the local public attributes of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLPA'},
            {'name': 'Total Number of Local Public Methods', 'description': 'Number of local (i.e. not inherited) public methods in the class, including the local methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLPM'},
            {'name': 'Total Number of Local Setters', 'description': 'Number of local (i.e. not inherited) setter methods in the class, including the local setter methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNLS'},
            {'name': 'Total Number of Methods', 'description': 'Number of methods in the class, including the inherited ones, as well as the inherited and local methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNM'},
            {'name': 'Total Number of Packages', 'description': 'Nmber of subpackages in the package, including all directly or indirectly contained subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPKG'},
            {'name': 'Total Number of Public Attributes', 'description': 'Number of public attributes in the class, including the inherited ones, as well as the inherited and local public attributes of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPA'},
            {'name': 'Total Number of Public Classes', 'description': 'Number of public classes in the package, including the public classes of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPCL'},
            {'name': 'Total Number of Public Enums', 'description': 'Number of public enums in the package, including the public enums of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPEN'},
            {'name': 'Total Number of Public Interfaces', 'description': 'Number of public interfaces in the package, including the public interfaces of its subpackages.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPIN'},
            {'name': 'Total Number of Public Methods', 'description': 'Number of public methods in the class, including the inherited ones, as well as the inherited and local public methods of its nested, anonymous, and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNPM'},
            {'name': 'Total Number of Setters', 'description': 'Number of setter methods in the class, including the inherited ones, as well as the inherited and local setter methods of its nested, anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNS'},
            {'name': 'Total Number of Statements', 'description': 'Number of statements in the method, including the statements of its anonymous and local classes.', 'domain': 'Size metrics', 'tool': 'SourceMeter', 'key': 'TNOS'},
            {'name': 'Clone Age', 'description': 'Number of previously analyzed revisions in which the clone class/clone instance was present + 1.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CA'},
            {'name': 'Clone Classes', 'description': 'Nmber of clone classes having at least one clone instance in the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CCL'},
            {'name': 'Clone Complexity', 'description': 'Sum of CCO of clone instances in the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CCO'},
            {'name': 'Clone Coverage', 'description': 'Ratio of code covered by code duplications in the source code element to the size of the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CC'},
            {'name': 'Clone Elimination Effort', 'description': 'Index of the effort required to eliminate all clones from the component.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CEE'},
            {'name': 'Clone Embeddedness', 'description': 'sum of incoming and outgoing references (function calls, variable references, type references) in the code fragment corresponding to the clone instance, weighted with the number of directory changes between the referenced code fragments.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CE'},
            {'name': 'Clone Instances', 'description': 'Number of clone instances in the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CI'},
            {'name': 'Clone Line Coverage', 'description': 'Ratio of code covered by code duplications in the source code element to the size of the source code element, expressed in terms of lines of code.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CLC'},
            {'name': 'Clone Lines of Code', 'description': 'Length of the clone instance expressed in terms of lines of code.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CLLOC'},
            {'name': 'Clone Logical Line Coverage', 'description': 'Ratio of code covered by code duplications in the source code element to the size of source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CLLC'},
            {'name': 'Clone Risk', 'description': 'Relative risk index of the existence of code duplications in the component.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CR'},
            {'name': 'Clone Variability', 'description': 'Instability of the clone class since it appeared.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'CV'},
            {'name': 'Lines of Duplicated Code', 'description': 'Number of code lines covered by code duplications in the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'LDC'},
            {'name': 'Logical Lines of Duplicated Code', 'description': 'Nmber of logical code lines covered by code duplications in the source code element.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'LLDC'},
            {'name': 'Normalized Clone Radius', 'description': 'Normalized average distance among clone instances belonging to the clone class.', 'domain': 'Clone metrics', 'tool': 'SourceMeter', 'key': 'NCR'},
            {'name': 'Command Injection', 'description': 'In case of command injection the attacker forces the application to execute manipulated OS commands.', 'domain': 'Vulnerability Rules', 'tool': 'SourceMeter', 'key': 'VH_CI'},
        ]
        
        created_sm = 0
        for metric_data in sourcemeter_metrics:
            metric, created = Metric.objects.get_or_create(
                key=metric_data['key'],
                tool='SourceMeter',
                defaults={
                    'name': metric_data['name'],
                    'description': metric_data.get('description', ''),
                    'domain': metric_data.get('domain', ''),
                }
            )
            if created:
                created_sm += 1
        
        self.stdout.write(self.style.SUCCESS(f'    {created_sm} métricas de SourceMeter creadas'))

        # ============================================
        # 3. CARGAR MÉTRICAS DE SONARQUBE (73 métricas)
        # ============================================
        self.stdout.write('\n Cargando métricas de SonarQube...')
        
        sonarqube_metrics = [
            {'name': 'Vulnerabilities', 'description': 'The total number of security issues.', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'vulnerabilities'},
            {'name': 'Vulnerabilities on new code', 'description': 'The total number of vulnerabilities raised for the first time on new code.', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'new_vulnerabilities'},
            {'name': 'Security rating', 'description': 'Rating related to security. (A = 0 vulnerability, B = at least one minor vulnerability, C = at least one major vulnerability, D = at least one critical vulnerability, E = at least one blocker vulnerability', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'security_rating'},
            {'name': 'Security rating on new code', 'description': 'Rating related to security on new code.', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'new_security_rating'},
            {'name': 'Security remediation effort', 'description': 'The effort to fix all vulnerabilities.', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'security_remediation_effort'},
            {'name': 'Security remediation effort on new code', 'description': 'The same as Security remediation effort but on new code.', 'domain': 'Security metrics', 'tool': 'SonarQube', 'key': 'new_security_remediation_effort'},
            {'name': 'Bugs', 'description': 'The total number of issues impacting the reliability (reliability issues).', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'bugs'},
            {'name': 'Bugs on new code', 'description': 'The total number of reliability issues raised for the first time on new code.', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'new_bugs'},
            {'name': 'Reliability rating', 'description': 'Rating related to reliability. (A = 0 bug, B = at least one minor bug, C = at least one major bug, D = at least one critical bug, E = at least one blocker bug).', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'reliability_rating'},
            {'name': 'Reliability rating on new code', 'description': 'Rating related to reliability on new code.', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'new_reliability_rating'},
            {'name': 'Reliability remediation effort', 'description': 'The effort to fix all reliability issues.', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'reliability_remediation_effort'},
            {'name': 'Reliability remediation effort on new code', 'description': 'The same as Reliability remediation effort but on new code.', 'domain': 'Reliability metrics', 'tool': 'SonarQube', 'key': 'new_reliability_remmediation_effort'},
            {'name': 'Code smells', 'description': 'The total number of issues impacting the maintainability (maintainability issues).', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'code_smells'},
            {'name': 'Code smells on new code', 'description': 'The total number of maintainability issues raised for the first time on new code.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'new_code_smells'},
            {'name': 'Technical debt', 'description': 'A measure of effort to fix all maintainability issues. See below.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'sqale_index'},
            {'name': 'Technical debt on new code', 'description': 'A measure of effort to fix the maintainability issues raised for the first time on new code.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'new_technical_debt'},
            {'name': 'Technical debt ratio', 'description': 'The ratio between the cost to develop the software and the cost to fix it. See below.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'sqale_debt_ratio'},
            {'name': 'Technical debt ratio on new code', 'description': 'The ratio between the cost to develop the code changed on new code and the cost of the issues linked to it.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'new_sqale_debt_ratio'},
            {'name': 'Maintainability rating', 'description': 'The rating related to the value of the technical debt ratio. See below.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'sqale_rating'},
            {'name': 'Maintainability rating on new code', 'description': 'The rating related to the value of the technical debt ratio on new code.', 'domain': 'Maintainability metrics', 'tool': 'SonarQube', 'key': 'new_squale_rating'},
            {'name': 'Coverage', 'description': 'A mix of line coverage and condition coverage.(How much of the source code has been covered by unit tests)', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'coverage'},
            {'name': 'Coverage on new code', 'description': 'This definition is identical to coverage but is restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_coverage'},
            {'name': 'Lines to cover', 'description': 'Coverable lines. The number of lines of code that could be covered by unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'lines_to_cover'},
            {'name': 'Lines to cover on new code', 'description': 'This definition is identical to lines to cover but restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_lines_to_cover'},
            {'name': 'Uncovered lines', 'description': 'The number of lines of code that are not covered by unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'uncovered_lines'},
            {'name': 'Uncovered lines on new code', 'description': 'This definition is identical to uncovered lines but restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_uncovered_lines'},
            {'name': 'Line coverage', 'description': 'Answers the question: Has this line of code been executed during the execution of the unit tests?', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'line_coverage'},
            {'name': 'Line coverage on new code', 'description': 'This definition is identical to line coverage but restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_line_coverage'},
            {'name': 'Line coverage hits', 'description': 'A list of covered lines.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'coverage_line_hist_data'},
            {'name': 'Condition coverage', 'description': 'Answers the following question on each line of code containing boolean expressions: Has each boolean expression been evaluated both to true and to false? ', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'branch_coverage'},
            {'name': 'Condition coverage on new code', 'description': 'This definition is identical to condition coverage but is restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_branch_coverage'},
            {'name': 'Condition coverage hits', 'description': 'A list of covered conditions.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'branch_coverage_hits_data'},
            {'name': 'Conditions by line', 'description': 'The number of conditions by line.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'conditions_by_line'},
            {'name': 'Covered conditions by line', 'description': 'Number of covered conditions by line.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'covered_conditions_by_line'},
            {'name': 'Uncovered conditions', 'description': 'The number of conditions that are not covered by unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'uncovered_conditions'},
            {'name': 'Uncovered conditions on new code', 'description': 'This definition is identical to Uncovered conditions but restricted to new or updated source code.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'new_uncovered_conditions'},
            {'name': 'Unit tests', 'description': 'The number of unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'tests'},
            {'name': 'Unit test errors', 'description': 'The number of unit tests that have failed.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'test_errors'},
            {'name': 'Unit test failures', 'description': 'The number of unit tests that have failed with an unexpected exception.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'test_failures'},
            {'name': 'Skipped unit tests', 'description': 'The number of skipped unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'skipped_tests'},
            {'name': 'Unit tests duration', 'description': 'The time required to execute all the unit tests.', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'test_execution_time'},
            {'name': 'Unit test success density (%)', 'description': 'test_success_density = (tests - (test_errors + test_failures)) / (tests) * 100', 'domain': 'Coverage metrics', 'tool': 'SonarQube', 'key': 'test_success_density'},
            {'name': 'Duplicated lines density (%) on new code', 'description': 'The same as duplicated lines density but on new code.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'duplicated_lines_density'},
            {'name': 'Duplicated lines', 'description': 'The number of lines involved in duplications.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'duplicated_lines'},
            {'name': 'Duplicated lines on new code', 'description': 'The number of lines involved in duplications on new code.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'new_duplicated_lines'},
            {'name': 'Duplicated blocks', 'description': 'The number of duplicated blocks of lines.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'duplicated_blocks'},
            {'name': 'Duplicated block on new code', 'description': 'The number of duplicated blocks of lines on new code.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'new_duplicated_blocks'},
            {'name': 'Duplicated files', 'description': 'The number of files involved in duplications.', 'domain': 'Duplications metrics', 'tool': 'SonarQube', 'key': 'duplicated_files'},
            {'name': 'New lines', 'description': 'The number of physical lines on new code (number of carriage returns).', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'new_lines'},
            {'name': 'Lines of code', 'description': 'The number of physical lines that contain at least one character which is neither a whitespace nor a tabulation nor part of a comment.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'ncloc'},
            {'name': 'Lines', 'description': 'The number of physical lines (number of carriage returns).', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'lines'},
            {'name': 'Statements', 'description': 'The number of statements.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'statements'},
            {'name': 'Functions', 'description': 'The number of functions.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'functions'},
            {'name': 'Classes', 'description': 'The number of classes (including nested classes, interfaces, enums, annotations, mixins, extensions, and extension types).', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'classes'},
            {'name': 'Files', 'description': 'The number of files. ', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'files'},
            {'name': 'Comment lines', 'description': 'The number of lines containing either comment or commented-out code. ', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'comment_lines'},
            {'name': 'Comments (%)', 'description': 'The comment lines density.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'comment_lines_density'},
            {'name': 'Lines of code per language', 'description': 'The non-commented lines of code distributed by language.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'ncloc_language_distribution'},
            {'name': 'Projects', 'description': 'The number of projects in a portfolio.', 'domain': 'Size metrics', 'tool': 'SonarQube', 'key': 'projects'},
            {'name': 'Cyclomatic complexity', 'description': 'A quantitative metric used to calculate the number of paths through the code.', 'domain': 'Complexity metrics', 'tool': 'SonarQube', 'key': 'complexity'},
            {'name': 'Cognitive complexity', 'description': 'A qualification of how hard it is to understand the code control flow.', 'domain': 'Complexity metrics', 'tool': 'SonarQube', 'key': 'cognitive_complexity'},
            {'name': 'Issues', 'description': 'The number of issues in all states.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'violations'},
            {'name': 'Issues on new code', 'description': 'The number of issues raised for the first time on new code.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'new_violations'},
            {'name': 'Accepted issues', 'description': 'The number of issues marked as Accepted.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'accepted_issues'},
            {'name': 'Open issues', 'description': 'The number of issues in the Openstatus.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'open_issues'},
            {'name': 'Accepted issues on new code', 'description': 'The number of Accepted issues on new code.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'new_accepted_issues'},
            {'name': 'False positive issues', 'description': 'The number of issues marked as False positive.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'false_positive_issues'},
            {'name': 'Blocker issues', 'description': 'Issues with a Blocker severity level.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'blocker_violations'},
            {'name': 'Critical issues', 'description': 'Issues with a Critical severity level.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'critical_violations'},
            {'name': 'Major issues', 'description': 'Issues with a Major severity level.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'major_violations'},
            {'name': 'Minor issues', 'description': 'Issues with a Minor severity level.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'minor_violations'},
            {'name': 'Info issues', 'description': 'Issues with an Info severity level.', 'domain': 'Issues metrics', 'tool': 'SonarQube', 'key': 'info_violations'},
        ]
        
        created_sq = 0
        for metric_data in sonarqube_metrics:
            metric, created = Metric.objects.get_or_create(
                key=metric_data['key'],
                tool='SonarQube',
                defaults={
                    'name': metric_data['name'],
                    'description': metric_data.get('description', ''),
                    'domain': metric_data.get('domain', ''),
                }
            )
            if created:
                created_sq += 1
        
        self.stdout.write(self.style.SUCCESS(f'    {created_sq} métricas de SonarQube creadas'))

        # ============================================
        # RESUMEN FINAL
        # ============================================
        total_metrics = Metric.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\n Datos iniciales poblados exitosamente!'))
        self.stdout.write(f'\n Total de métricas en BD: {total_metrics}')
        self.stdout.write('   - SourceMeter: 99 métricas')
        self.stdout.write('   - SonarQube: 73 métricas')
        self.stdout.write('\n Usuario admin creado con credenciales:')
        self.stdout.write('   - Usuario: admin')
        self.stdout.write('   - Contraseña: admin')
        self.stdout.write('     Cambiar la contraseña en producción!\n')
