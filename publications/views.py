from django.shortcuts import render
from rest_framework import viewsets
from rest_framework import (generics,permissions,renderers,)

from commoninfo.permissions import IsOwnerOrReadOnly,CustomDjangoModelPermissions
from .models import (StgResourceType, StgKnowledgeProduct, StgProductDomain,)
from publications.serializers import (StgResourceTypeSerializer,
    StgKnowledgeProductSerializer,StgKnowledgeDomainSerializer,)

class StgResourceTypeViewSet(viewsets.ModelViewSet):
    serializer_class = StgResourceTypeSerializer
    permission_classes = (permissions.IsAuthenticated,
        CustomDjangoModelPermissions,)

    def get_queryset(self):
        language = self.request.LANGUAGE_CODE # get the en, fr or pt from the request
        return StgResourceType.objects.filter(
            translations__language_code=language).order_by(
            'translations__name').distinct()



class StgKnowledgeDomainViewSet(viewsets.ModelViewSet):
    serializer_class = StgKnowledgeDomainSerializer
    permission_classes = (permissions.IsAuthenticated,
        CustomDjangoModelPermissions,)

    def get_queryset(self):
        language = self.request.LANGUAGE_CODE # get the en, fr or pt from the request
        return StgProductDomain.objects.filter(
            translations__language_code=language).order_by(
            'translations__name').distinct()



class StgKnowledgeProductViewSet(viewsets.ModelViewSet):
    serializer_class = StgKnowledgeProductSerializer
    permission_classes = (permissions.IsAuthenticated,
        CustomDjangoModelPermissions,IsOwnerOrReadOnly)

    def get_queryset(self):
        language = self.request.LANGUAGE_CODE # get the en, fr or pt from the request
        queryset =  StgKnowledgeProduct.objects.filter(
                    translations__language_code=language).order_by(
                    'translations__title').distinct()
        user = self.request.user.id
        groups = list(self.request.user.groups.values_list('user', flat=True))
        location = self.request.user.location_id
        if self.request.user.is_superuser:
            qs=queryset
        elif user in groups: # Match fact location field to that of logged user
            qs=queryset.filter(location=location)
        else:
            qs=queryset.filter(user=user)
        return qs
