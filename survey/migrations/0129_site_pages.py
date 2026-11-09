"""Pages of a site (change site-pages, #628; epic #348 wave C).

Every existing site becomes a one-page site: a home page is created for it and its blocks are
attached to it in their order, then `SiteBlock.page` becomes required. Additive; the reverse drops
the column and the table (blocks keep `site` and `order`, so nothing but extra pages is lost).
"""
import django.db.models.deletion
from django.db import migrations, models


HOME_TITLES = {'ru': 'Главная', 'de': 'Startseite', 'fr': 'Accueil', 'es': 'Inicio', 'pl': 'Strona główna',
               'pt': 'Início', 'it': 'Home'}


def create_home_pages(apps, schema_editor):
    Site = apps.get_model('survey', 'Site')
    SitePage = apps.get_model('survey', 'SitePage')
    SiteBlock = apps.get_model('survey', 'SiteBlock')
    for site in Site.objects.all().only('id', 'language'):
        home = SitePage.objects.create(site_id=site.pk, title=HOME_TITLES.get(site.language, 'Home'),
                                       slug='', order=0, is_home=True)
        SiteBlock.objects.filter(site_id=site.pk).update(page=home)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0128_site_gallery_compare'),
    ]

    operations = [
        migrations.CreateModel(
            name='SitePage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=60)),
                ('slug', models.SlugField(blank=True, default='', max_length=64)),
                ('order', models.PositiveIntegerField(default=0)),
                ('in_menu', models.BooleanField(db_default=True, default=True)),
                ('is_home', models.BooleanField(db_default=False, default=False)),
                ('translations', models.JSONField(blank=True, db_default={}, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages',
                                           to='survey.site')),
            ],
            options={'ordering': ('order', 'id')},
        ),
        migrations.AddConstraint(
            model_name='sitepage',
            constraint=models.UniqueConstraint(condition=models.Q(('is_home', True)), fields=('site',),
                                               name='sitepage_one_home'),
        ),
        migrations.AddConstraint(
            model_name='sitepage',
            constraint=models.UniqueConstraint(condition=models.Q(('is_home', False)), fields=('site', 'slug'),
                                               name='sitepage_slug_unique'),
        ),
        migrations.AddField(
            model_name='siteblock',
            name='page',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='blocks',
                                    to='survey.sitepage'),
        ),
        migrations.RunPython(create_home_pages, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='siteblock',
            name='page',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks',
                                    to='survey.sitepage'),
        ),
    ]
