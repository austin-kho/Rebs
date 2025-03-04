from datetime import datetime

from django_filters import BooleanFilter
from django_filters.rest_framework import FilterSet
from rest_framework import viewsets, status
from rest_framework.response import Response

from ..pagination import PageNumberPaginationOneHundred, PageNumberPaginationThreeThousand
from ..permission import *
from ..serializers.docs import *


# Docs --------------------------------------------------------------------------

class DocTypeViewSet(viewsets.ModelViewSet):
    queryset = DocType.objects.all()
    serializer_class = DocTypeSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)
    filterset_fields = ('doc_type', 'active')


class LawSuitCaseFilterSet(FilterSet):
    is_com = BooleanFilter(field_name='project', lookup_expr='isnull', label='본사')
    in_progress = BooleanFilter(field_name='case_end_date', lookup_expr='isnull', label='진행중')

    class Meta:
        model = LawsuitCase
        fields = ('company', 'is_com', 'project', 'sort', 'level', 'court', 'in_progress')


class LawSuitCaseBase(viewsets.ModelViewSet):
    queryset = LawsuitCase.objects.all()
    serializer_class = LawSuitCaseSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)
    pagination_class = PageNumberPaginationOneHundred
    filterset_class = LawSuitCaseFilterSet
    search_fields = ('other_agency', 'case_number', 'case_name', 'plaintiff', 'plaintiff_attorney',
                     'defendant', 'defendant_attorney', 'case_start_date', 'case_end_date', 'summary')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LawSuitCaseViewSet(LawSuitCaseBase):
    def get_queryset(self):
        queryset = LawsuitCase.objects.all()
        related = self.request.query_params.get('related_case')
        if related:
            queryset = queryset.filter(Q(pk=related) | Q(related_case=related))
        return queryset


class AllLawSuitCaseViewSet(LawSuitCaseViewSet):
    serializer_class = SimpleLawSuitCaseSerializer
    pagination_class = PageNumberPaginationThreeThousand


class DocumentFilterSet(FilterSet):
    is_com = BooleanFilter(field_name='project', lookup_expr='isnull', label='본사')

    class Meta:
        model = Document
        fields = ('company', 'project', 'is_com', 'issue_project', 'doc_type', 'category', 'lawsuit', 'user')


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)
    pagination_class = PageNumberPaginationOneHundred
    filterset_class = DocumentFilterSet
    search_fields = (
        'lawsuit__case_number', 'lawsuit__case_name', 'title',
        'content', 'links__link', 'files__file', 'user__username')

    def copy_and_create(self, request, *args, **kwargs):
        # 복사할 행의 ID를 저장한다.
        origin_pk = kwargs.get('pk')
        project = request.data.get('project')
        doc_type = request.data.get('doc_type')

        try:
            # 기존 행을 가져와서 복사한다.
            org_instance = Document.objects.get(pk=origin_pk)

            add_text = f'<br /><br /><p>[이 게시물은 {self.request.user.username} 님에 의해 {datetime.now()} {org_instance.board.name} 에서 복사됨]</p>'

            # 기존 행의 정보를 사용하여 새로운 행을 생성한다.
            new_instance_data = {
                'company': org_instance.company.pk,
                'project': project if project else None,
                'doc_type': doc_type,
                'category': org_instance.category.pk if org_instance.category else None,
                'lawsuit': org_instance.lawsuit.pk if org_instance.lawsuit else None,
                'title': org_instance.title,
                'execution_date': org_instance.execution_date if org_instance.execution_date else None,
                'content': org_instance.content + add_text,
            }

            # Serializer를 사용해 새로운 행을 생성하고 저장한다.
            serializer = DocumentSerializer(data=new_instance_data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Document.DoesNotExist:
            return Response({'detail': 'Original Document object does not exist'}, status=status.HTTP_404_NOT_FOUND)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        instance.soft_delete()
        return Response({'status': 'soft-deleted'}, status=status.HTTP_200_OK)


class LinkViewSet(viewsets.ModelViewSet):
    queryset = Link.objects.all()
    serializer_class = LinkSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)


class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)


class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = (permissions.IsAuthenticated, IsProjectStaffOrReadOnly)


class DocsInTrashViewSet(DocumentViewSet):
    queryset = Document.all_objects.filter(deleted__isnull=False)
    serializer_class = DocumentInTrashSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
