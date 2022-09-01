from django.db import models
import uuid
from django.utils import timezone
from django.utils.translation import gettext_lazy as _ # The _ is alias for gettext
from parler.models import TranslatableModel, TranslatedFields
from django.core.exceptions import ValidationError
from django.core.validators import (RegexValidator,MinValueValidator,
    MaxValueValidator)
from aho_datacapturetool.settings import *
from data_wizard.sources.models import FileSource,URLSource
from regions.models import StgLocation,StgLocationCodes
from authentication.models import CustomUser


class StgPeriodType(models.Model):
    period_id = models.AutoField(primary_key=True)
    uuid = models.CharField(_('Unique ID'),unique=True,max_length=36,
        blank=False,null=False,default=uuid.uuid4,editable=False,)
    code = models.CharField(unique=True, max_length=50)
    name = models.CharField(_('Period Name'),max_length=50, blank=False,
        null=False,)
    shortname = models.CharField(_('Short Name'),max_length=50, blank=True,
        null=True,)
    description = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = 'Date Created')
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = 'Date Modified')

    class Meta:
        managed = True
        db_table = 'stg_periodicity_type'
        verbose_name = _('Period Type')
        verbose_name_plural = _('   Period Types')
        ordering = ('name', )

    def __str__(self):
        return self.name #ddisplay disagregation options

    def clean(self):
        if StgPeriodType.objects.filter(
            name=self.name).count() and not self.period_id:
            raise ValidationError({'name':_(
                'Sorry! Period type with the same name exists')})

    def save(self, *args, **kwargs):
        super(StgPeriodType, self).save(*args, **kwargs)


class StgCustomNationalObservatory(models.Model):
    number_regex = RegexValidator(
        regex=r'^[0-9]{8,15}$', message="Format:'999999999' min 8, maximum 15.")
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', message="Please use correct phone number format")

    observatory_id = models.AutoField(primary_key=True)
    uuid = uuid = models.CharField(_('Unique ID'),unique=True,max_length=36,
        blank=False,null=False,default=uuid.uuid4,editable=False)
    code = models.CharField(unique=True, blank=True,null=False,max_length=45)
    user = models.ForeignKey(CustomUser, models.PROTECT,blank=True,
		verbose_name = 'Admin User (Email)',)
    location = models.ForeignKey(StgLocationCodes, models.PROTECT,
        verbose_name = _('Country'),)
    name = models.CharField(_('Title'),max_length=500,blank=False,
        null=False)
    custom_header = models.CharField(_('Custom Header'),max_length=1000,
        blank=True, null=True,)
    custom_footer = models.CharField(_('Custom Footer'),max_length=1000,
        blank=True, null=True,)
    announcement = models.TextField(_('Announcements'),blank=True,null=True)
    coat_arms = models.ImageField(_('Coat of Arms'),upload_to='dev/images/',
        blank=True,)
    address = models.CharField(_('Physical Address'),max_length=500,blank=True,
        null=True)  # Field name made lowercase.
    email = models.EmailField(_('Email'),unique=True,max_length=250,
        blank=True,null=True)  # Field name made lowercase.
    phone_code = models.CharField(_('Phone Code'), max_length=5, blank=True,
        help_text=_("Specific country code for the phone number such as +242 is \
        automatically retrieved from database of AFRO member countries"))
    phone_part = models.CharField(_('Phone Number'),validators=[number_regex],
        max_length=15, blank=True) # validators should be a list
    phone_number = models.CharField(_('Telephone'),validators=[phone_regex],
        max_length=15, null=True,blank=True) # validators should be a list
    url = models.URLField(_('Web (URL)'),blank=True, null=True,max_length=2083)
    date_created = models.DateTimeField(_('Date Created'),blank=True, null=True,
        auto_now_add=True)
    date_lastupdated = models.DateTimeField(_('Date Modified'),blank=True,
        null=True, auto_now=True)

    class Meta:
        managed = True
        db_table = 'stg_national_observatory'
        verbose_name = _('Health Observatory')
        verbose_name_plural = _('    Health Observatories')
        ordering = ('name',)

    def __str__(self):
        return self.name #display the data element name

    def get_phone(self):
        # Assign pone code to a field in related model using dot operator 4/3/2021
        self.phone_code = self.location.country_code
        phone_number = self.phone_number
        if self.phone_part is not None or self.phone_part!='':
            phone_number=(self.phone_code+self.phone_part)
        else:
            phone_number=None
        return phone_number

    def clean(self):
        if StgCustomNationalObservatory.objects.filter(name=self.name).count() and not \
            self.observatory_id and not self.location:
            raise ValidationError({'name':_('NHO  with the same name exists')})

    def save(self, *args, **kwargs):
        self.phone_number = self.get_phone()
        super(StgCustomNationalObservatory, self).save(*args, **kwargs)



class StgCategoryParent(TranslatableModel):
    """This model has stgcategory data"""
    category_id = models.AutoField(_('Category Name'),primary_key=True,)
    uuid = uuid = models.CharField(_('Unique ID'),unique=True,
        max_length=36, blank=False,null=False,default=uuid.uuid4,editable=False,)
    translations = TranslatedFields(
        name = models.CharField(_('Category Name'),max_length=230, blank=False,
            null=False),  # Field name made lowercase.
        shortname = models.CharField(_('Short Name'),max_length=50, blank=True,
            null=True,),
        description = models.TextField(blank=True, null=True)  # Field name made lowercase.
    )
    code = models.CharField(unique=True, max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = 'Date Created')
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = 'Date Modified')

    class Meta:
        managed = True
        db_table = 'stg_category_parent'
        verbose_name = _('Disaggregation Category')
        verbose_name_plural = _('  Disaggregation Categories')
        ordering = ('translations__name',)

    def __str__(self):
        return self.name #ddisplay disagregation Categories


class StgCategoryoption(TranslatableModel):
    categoryoption_id = models.AutoField(primary_key=True)
    uuid = uuid = models.CharField(unique=True,max_length=36, blank=False,
        null=False,default=uuid.uuid4,editable=False, verbose_name =_('Unique ID'))
    category = models.ForeignKey(StgCategoryParent, models.PROTECT,
        verbose_name = _('Category Name'))
    translations = TranslatedFields(
        name = models.CharField(max_length=230, blank=False, null=False,
            verbose_name = _('Modality Name')),
        shortname = models.CharField(max_length=50, blank=True, null=True,
            verbose_name = _('Short Name')),
        description = models.TextField(blank=True, null=True)
    )
    code = models.CharField(unique=True,max_length=50, blank=True, null=False)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = 'Date Created')
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = 'Date Modified')

    class Meta:
        managed = True
        db_table = 'stg_categoryoption'
        verbose_name = _('Disaggregation Option')
        verbose_name_plural = _('   Disaggregation Options')
        ordering = ('translations__name',)

    def __str__(self):
        return self.name #ddisplay disagregation options

class StgDatasource(TranslatableModel):
    LEVEL_CHOICES = ( #choices for approval of indicator data by authorized users
        ('global', _('Global')),
        ('regional',_('Regional')),
        ('national',_('National')),
        ('sub-national',_('Sub-national')),
        ('unspecified',_('Non-specific'))
    )
    datasource_id = models.AutoField(primary_key=True)
    uuid = uuid = models.CharField(unique=True,max_length=36, blank=False,
        null=False,default=uuid.uuid4,editable=False, verbose_name = 'Unique ID')
    translations = TranslatedFields(
        name = models.CharField(max_length=230, blank=False, null=False,
            verbose_name =_('Data Source')),  # Field name made lowercase.
        shortname = models.CharField(max_length=50, blank=True, null=True,
            verbose_name = _('Short Name')),  # Field name made lowercase.
        level = models.CharField(max_length=20,blank=False, null=False,
            choices= LEVEL_CHOICES,verbose_name =_('Source Level'),
            default=LEVEL_CHOICES[2][0],
            help_text=_("Level can be global, regional, national, subnational")),
        description = models.TextField( blank=False, null=False,
            default=_('No definition'))
    )
    code = models.CharField(unique=True, max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = _('Date Created'))
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = _('Date Modified'))

    class Meta:
        managed = True
        db_table = 'stg_datasource'
        verbose_name = _('Data Source')
        verbose_name_plural = _('    Data Sources')
        ordering = ('translations__name',)

    def __str__(self):
        return self.name #display the data source name

    def clean(self): # Don't allow end_period to be greater than the start_period.
        if StgDatasource.objects.filter(
            translations__name=self.name).count() and not self.datasource_id:
            raise ValidationError({'name':_('Sorry! This data source exists')})


class StgValueDatatype(TranslatableModel):
    valuetype_id = models.AutoField(primary_key=True)  # Field name made lowercase.
    uuid = uuid = models.CharField(unique=True,max_length=36, blank=False,
        null=False,default=uuid.uuid4,editable=False,verbose_name=_('Unique ID'))
    translations = TranslatedFields(
        name = models.CharField(max_length=50, verbose_name =_('Value Name')),
        shortname = models.CharField(max_length=50, blank=True, null=True,
            verbose_name =_('Short Name')),
        description = models.TextField(blank=True, null=True)
    )
    code = models.CharField(unique=True, max_length=50)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = _('Date Created'))
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = _('Date Modified'))

    class Meta:
         managed = True
         db_table = 'stg_value_datatype'
         verbose_name = _(' Data Value')
         verbose_name_plural = _('Data Value Types')
         ordering = ('translations__name',)

    def __str__(self):
         return self.name #ddisplay disagregation options


class StgMeasuremethod(TranslatableModel):
    measuremethod_id = models.AutoField(primary_key=True)
    uuid = uuid = models.CharField(_('Unique ID'),unique=True,max_length=36,
        blank=False, null=False,default=uuid.uuid4,editable=False)
    translations = TranslatedFields(
        name = models.CharField(_('Measure Name'),max_length=230, blank=False,
            null=False,help_text=_("Name can be indicator types like unit, \
            Percentage, Per Thousand, Per Ten Thousand,Per Hundred Thousand etc")),
        measure_value = models.DecimalField(_('Ratio'),max_digits=50,
            decimal_places=0,blank=True, null=True,help_text=_("Ratio can be \
            factors like 1 for unit, 100, 1000,10000 or higher values")),
        description = models.TextField(_('Description'),max_length=200,
        blank=True, null=True)
    )
    code = models.CharField(max_length=50,unique=True, blank=True, null=False)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True,
        verbose_name = _('Date Created'))
    date_lastupdated = models.DateTimeField(blank=True, null=True, auto_now=True,
        verbose_name = _('Date Modified'))

    class Meta:
        managed = True
        db_table = 'stg_measuremethod'
        verbose_name = _('Measure Type')
        verbose_name_plural = _(' Measure Types')
        ordering = ('translations__name',)

    def __str__(self):
        return self.name #ddisplay measurement methods


"""
These model classes inherits from data_wizard sources package.The purpose of
inheriting the models is to add location field to the sources database tables
"""
class FileSource(FileSource):
    location = models.ForeignKey(StgLocation, models.PROTECT,blank=False,
        verbose_name = _('Location Name'),)
    user = models.ForeignKey(CustomUser, models.PROTECT,
        verbose_name='User Name (Email)') # request helper field
    url = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name or self.file.name

    """
    This method appends the relative filename path to Azure blob url before save
    """

    def get_fileurl(self):
        base_url=f'https://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/'
        file_name = self.file.name
        if self.url is None or self.url =='':
            return (base_url+'datawizard/'+file_name)
        return self.file.url

    """
    This method overrides the save method to store the derived field into database.
    Note that the last line calls the super class to save the URL value
    """
    def save(self, *args, **kwargs):
        self.url = self.get_fileurl()
        super(FileSource, self).save(*args, **kwargs)


class URLSource(URLSource): # check the inher
    location = models.ForeignKey(StgLocation, models.PROTECT,blank=False,
        verbose_name = _('Location Name'),)
    user = models.ForeignKey(CustomUser, models.PROTECT,
        verbose_name='User Name (Email)') # request helper field
    file = models.ForeignKey(FileSource, on_delete=models.CASCADE,
                        related_name="link")

    def __str__(self):
        return self.name or self.url

    def get_url(self):
        if self.url is None or self.url =='':
            return self.file.url
        return self.url

    def save(self, *args, **kwargs):
        self.url = self.get_url()
        return super(URLSource, self).save(*args, **kwargs)
