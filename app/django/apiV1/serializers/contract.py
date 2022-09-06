from django.db import transaction
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist

from contract.models import (OrderGroup, Contract, Contractor,
                             ContractorAddress, ContractorContact, ContractorRelease)
from cash.models import ProjectBankAccount, ProjectCashBook, InstallmentPaymentOrder
from project.models import Project, HouseUnit, KeyUnit
from rebs.models import ProjectAccountSort, ProjectAccountD1, ProjectAccountD2
from .project import SimpleUnitTypeSerializer
from .cash import SimpleInstallmentOrderSerializer, SimpleOrderGroupSerializer


# Contract --------------------------------------------------------------------------
class OrderGroupSerializer(serializers.ModelSerializer):
    sort_desc = serializers.CharField(source='get_sort_display', read_only=True)

    class Meta:
        model = OrderGroup
        fields = ('pk', 'project', 'order_number', 'sort', 'sort_desc', 'order_group_name')


class HouseUnitInKeyUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseUnit
        fields = ('pk', '__str__', 'floor_type')


class KeyUnitInContractSerializer(serializers.ModelSerializer):
    houseunit = HouseUnitInKeyUnitSerializer()

    class Meta:
        model = KeyUnit
        fields = ('pk', 'unit_code', 'houseunit')


class AddressInContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorAddress
        fields = ('pk', 'id_zipcode', 'id_address1', 'id_address2', 'id_address3',
                  'dm_zipcode', 'dm_address1', 'dm_address2', 'dm_address3')


class ContactInContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorContact
        fields = ('pk', 'cell_phone', 'home_phone', 'other_phone', 'email')


class ContractorInContractSerializer(serializers.ModelSerializer):
    contractoraddress = AddressInContractorSerializer()
    contractorcontact = ContactInContractorSerializer()

    class Meta:
        model = Contractor
        fields = (
            'pk', 'name', 'birth_date', 'gender', 'is_registed', 'contractoraddress',
            'contractorcontact', 'status', 'reservation_date', 'contract_date', 'note')


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('pk', 'project', 'order_group', 'unit_type', 'serial_number', 'activation')


class ProjectCashBookInContractSerializer(serializers.ModelSerializer):
    installment_order = SimpleInstallmentOrderSerializer()

    class Meta:
        model = ProjectCashBook
        fields = ('pk', 'deal_date', 'income', 'bank_account', 'trader', 'installment_order')


class ContractSetSerializer(serializers.ModelSerializer):
    keyunit = KeyUnitInContractSerializer(read_only=True)
    contractor = ContractorInContractSerializer(read_only=True)
    payments = serializers.SerializerMethodField(read_only=True)
    order_group_desc = SimpleOrderGroupSerializer(source='order_group', read_only=True)
    unit_type_desc = SimpleUnitTypeSerializer(source='unit_type', read_only=True)

    class Meta:
        model = Contract
        fields = (
            'pk', 'project', 'order_group', 'unit_type', 'serial_number', 'activation',
            'keyunit', 'contractor', 'payments', 'order_group_desc', 'unit_type_desc')

    def get_payments(self, instance):
        payments = instance.payments.filter(project_account_d2__lte=2).order_by('deal_date', 'id')
        return ProjectCashBookInContractSerializer(payments, many=True, read_only=True).data

    @transaction.atomic
    def create(self, validated_data):
        # 1. 계약정보 테이블 입력
        contract = Contract.objects.create(**validated_data)
        contract.save()

        # 2. 계약 유닛 연결
        keyunit_data = self.initial_data.get('keyunit')
        keyunit = KeyUnit.objects.get(pk=keyunit_data)
        keyunit.contract = contract
        keyunit.save()

        # 3. 동호수 연결
        house_unit_data = self.initial_data.get('houseunit')
        house_unit = HouseUnit.objects.get(pk=house_unit_data)
        house_unit.key_unit = keyunit
        house_unit.save()

        # 4. 계약자 정보 테이블 입력
        contractor_name = self.initial_data.get('name')
        contractor_birth_date = self.initial_data.get('birth_date')
        contractor_gender = self.initial_data.get('gender')
        contractor_is_registed = self.initial_data.get('is_registed')
        contractor_status = self.initial_data.get('status')
        contractor_reservation_date = self.initial_data.get('reservation_date')
        contractor_contract_date = self.initial_data.get('contract_date')
        contractor_note = self.initial_data.get('note')

        contractor = Contractor(contract=contract,
                                name=contractor_name,
                                birth_date=contractor_birth_date,
                                gender=contractor_gender,
                                is_registed=contractor_is_registed,
                                status=contractor_status,
                                reservation_date=contractor_reservation_date,
                                contract_date=contractor_contract_date,
                                note=contractor_note)
        contractor.save()

        # 5. 계약자 주소 테이블 입력
        address_id_zipcode = self.initial_data.get('id_zipcode')
        address_id_address1 = self.initial_data.get('id_address1')
        address_id_address2 = self.initial_data.get('id_address2')
        address_id_address3 = self.initial_data.get('id_address3')
        address_dm_zipcode = self.initial_data.get('dm_zipcode')
        address_dm_address1 = self.initial_data.get('dm_address1')
        address_dm_address2 = self.initial_data.get('dm_address2')
        address_dm_address3 = self.initial_data.get('dm_address3')

        contractorAddress = ContractorAddress(contractor=contractor,
                                              id_zipcode=address_id_zipcode,
                                              id_address1=address_id_address1,
                                              id_address2=address_id_address2,
                                              id_address3=address_id_address3,
                                              dm_zipcode=address_dm_zipcode,
                                              dm_address1=address_dm_address1,
                                              dm_address2=address_dm_address2,
                                              dm_address3=address_dm_address3)
        contractorAddress.save()

        # 6. 계약자 연락처 테이블 입력
        contact_cell_phone = self.initial_data.get('cell_phone')
        contact_home_phone = self.initial_data.get('home_phone')
        contact_other_phone = self.initial_data.get('other_phone')
        contact_email = self.initial_data.get('email')

        contractorContact = ContractorContact(contractor=contractor,
                                              cell_phone=contact_cell_phone,
                                              home_phone=contact_home_phone,
                                              other_phone=contact_other_phone,
                                              email=contact_email)
        contractorContact.save()

        # 7. 계약금 -- 수납 정보 테이블 입력
        if self.initial_data.get('deal_date'):
            project = self.initial_data.get('project')
            payment_project = Project.objects.get(pk=project)
            order_group = self.initial_data.get('order_group')
            payment_account_d1 = ProjectAccountD1.objects.get(pk=order_group.get('sort'))
            payment_account_d2 = ProjectAccountD2.objects.get(pk=order_group.get('sort'))
            ins_order = self.initial_data.get('installment_order')
            payment_installment_order = InstallmentPaymentOrder.objects.get(pk=ins_order)
            payment_serial_number = self.initial_data.get('serial_number')
            payment_trader = self.initial_data.get('trader')
            bank_account = self.initial_data.get('bank_account')
            payment_bank_account = ProjectBankAccount.objects.get(pk=bank_account)
            payment_income = self.initial_data.get('income')
            payment_deal_date = self.initial_data.get('deal_date')

            down_payment = ProjectCashBook(project=payment_project,
                                           sort=ProjectAccountSort.objects.get(pk=1),
                                           project_account_d1=payment_account_d1,
                                           project_account_d2=payment_account_d2,
                                           is_contract_payment=True,
                                           contract=contract,
                                           installment_order=payment_installment_order,
                                           content=f'{contractor_name}[{payment_serial_number}] 대금납부',
                                           trader=payment_trader,
                                           bank_account=payment_bank_account,
                                           income=payment_income,
                                           deal_date=payment_deal_date)
            down_payment.save()

        return contract

    @transaction.atomic
    def update(self, instance, validated_data):
        # 1. 계약정보 테이블 입력
        instance.__dict__.update(**validated_data)
        instance.save()

        # 1-2. 종전 동호수 연결 해제
        keyunit_data = self.initial_data.get('keyunit')
        house_unit_data = self.initial_data.get('houseunit')

        if instance.keyunit.pk != keyunit_data:  # 키유닛이 수정된 경우
            try:
                old_houseunit = instance.keyunit.houseunit
                if old_houseunit != house_unit_data:  # 동호수도 수정된 경우
                    old_houseunit.key_unit = None
                    old_houseunit.save()
            except ObjectDoesNotExist:
                pass

            # 2. 계약 유닛 연결
            old_keyunit = instance.keyunit
            old_keyunit.contract = None  # 종전 계약의 계약유닛 삭제
            old_keyunit.save()

            keyunit = KeyUnit.objects.get(pk=keyunit_data)
            keyunit.contract = instance
            keyunit.save()

            # 3. 동호수 연결
            house_unit = HouseUnit.objects.get(pk=house_unit_data)
            house_unit.key_unit = keyunit  # 동호수를 키유닛과 연결
            house_unit.save()
        else:
            try:
                old_houseunit = instance.keyunit.houseunit
                if old_houseunit != house_unit_data:  # 동호수만 수정된 경우
                    old_houseunit.key_unit = None
                    old_houseunit.save()

                    # 3. 동호수 연결
                    house_unit = HouseUnit.objects.get(pk=house_unit_data)
                    house_unit.key_unit = instance.keyunit  # 동호수를 기존 키유닛과 연결
                    house_unit.save()
            except ObjectDoesNotExist:
                pass

        # 4. 계약자 정보 테이블 입력
        contractor_name = self.initial_data.get('name')
        contractor_birth_date = self.initial_data.get('birth_date')
        contractor_gender = self.initial_data.get('gender')
        contractor_is_registed = self.initial_data.get('is_registed')
        contractor_status = self.initial_data.get('status')
        contractor_reservation_date = self.initial_data.get('reservation_date')
        contractor_contract_date = self.initial_data.get('contract_date')
        contractor_note = self.initial_data.get('note')

        contractor = Contractor.objects.get(contract=instance)
        contractor.name = contractor_name
        contractor.birth_date = contractor_birth_date
        contractor.gender = contractor_gender
        contractor.is_registed = contractor_is_registed
        contractor.status = contractor_status
        contractor.reservation_date = contractor_reservation_date
        contractor.contract_date = contractor_contract_date
        contractor.note = contractor_note
        contractor.save()

        # 5. 계약자 주소 테이블 입력
        address_id_zipcode = self.initial_data.get('id_zipcode')
        address_id_address1 = self.initial_data.get('id_address1')
        address_id_address2 = self.initial_data.get('id_address2')
        address_id_address3 = self.initial_data.get('id_address3')
        address_dm_zipcode = self.initial_data.get('dm_zipcode')
        address_dm_address1 = self.initial_data.get('dm_address1')
        address_dm_address2 = self.initial_data.get('dm_address2')
        address_dm_address3 = self.initial_data.get('dm_address3')

        contractor_address = ContractorAddress.objects.get(contractor=contractor)
        contractor_address.id_zipcode = address_id_zipcode
        contractor_address.id_address1 = address_id_address1
        contractor_address.id_address2 = address_id_address2
        contractor_address.id_address3 = address_id_address3
        contractor_address.dm_zipcode = address_dm_zipcode
        contractor_address.dm_address1 = address_dm_address1
        contractor_address.dm_address2 = address_dm_address2
        contractor_address.dm_address3 = address_dm_address3
        contractor_address.save()

        # 6. 계약자 연락처 테이블 입력
        contact_cell_phone = self.initial_data.get('cell_phone')
        contact_home_phone = self.initial_data.get('home_phone')
        contact_other_phone = self.initial_data.get('other_phone')
        contact_email = self.initial_data.get('email')

        contractor_contact = ContractorContact.objects.get(contractor=contractor)
        contractor_contact.cell_phone = contact_cell_phone
        contractor_contact.home_phone = contact_home_phone
        contractor_contact.other_phone = contact_other_phone
        contractor_contact.email = contact_email
        contractor_contact.save()

        # 7. 계약금 -- 수납 정보 테이블 입력
        if self.initial_data.get('deal_date'):
            payment_id = self.initial_data.get('payment')
            project = self.initial_data.get('project')
            payment_project = Project.objects.get(pk=project)
            order_group = self.initial_data.get('order_group')
            payment_account_d1 = ProjectAccountD1.objects.get(pk=order_group.get('sort'))
            payment_account_d2 = ProjectAccountD2.objects.get(pk=order_group.get('sort'))
            ins_order = self.initial_data.get('installment_order')
            payment_installment_order = InstallmentPaymentOrder.objects.get(pk=ins_order)
            payment_serial_number = self.initial_data.get('serial_number')
            payment_trader = self.initial_data.get('trader')
            bank_account = self.initial_data.get('bank_account')
            payment_bank_account = ProjectBankAccount.objects.get(pk=bank_account)
            payment_income = self.initial_data.get('income')
            payment_deal_date = self.initial_data.get('deal_date')

            if payment_id:
                update_payment = ProjectCashBook.objects.get(pk=payment_id)
                update_payment.trader = payment_trader
                update_payment.bank_account = payment_bank_account
                update_payment.income = payment_income
                update_payment.deal_date = payment_deal_date
                update_payment.save()
            else:
                create_payment = ProjectCashBook(project=payment_project,
                                                 sort=ProjectAccountSort.objects.get(pk=1),
                                                 project_account_d1=payment_account_d1,
                                                 project_account_d2=payment_account_d2,
                                                 is_contract_payment=True,
                                                 contract=instance,
                                                 installment_order=payment_installment_order,
                                                 content=f'{contractor_name}[{payment_serial_number}] 대금납부',
                                                 trader=payment_trader,
                                                 bank_account=payment_bank_account,
                                                 income=payment_income,
                                                 deal_date=payment_deal_date)
                create_payment.save()

        return instance


class SubsSummarySerializer(serializers.ModelSerializer):
    unit_type = serializers.IntegerField()
    num_cont = serializers.IntegerField()

    class Meta:
        model = Contract
        fields = ('unit_type', 'num_cont')


class ContSummarySerializer(serializers.ModelSerializer):
    order_group = serializers.IntegerField()
    unit_type = serializers.IntegerField()
    num_cont = serializers.IntegerField()

    class Meta:
        model = Contract
        fields = ('order_group', 'unit_type', 'num_cont')


class ContractInContractorSerializer(serializers.ModelSerializer):
    keyunit = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Contract
        fields = ('pk', 'serial_number', 'keyunit')


class ContractorSerializer(serializers.ModelSerializer):
    contractorrelease = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Contractor
        fields = ('pk', 'contract', 'name', '__str__', 'birth_date', 'gender', 'is_registed',
                  'status', 'reservation_date', 'contract_date', 'note', 'contractorrelease')


class ContractorAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorAddress
        fields = ('pk', 'contractor', 'id_zipcode', 'id_address1', 'id_address2', 'id_address3',
                  'dm_zipcode', 'dm_address1', 'dm_address2', 'dm_address3')


class ContractorContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorContact
        fields = ('pk', 'contractor', 'cell_phone', 'home_phone', 'other_phone', 'email')


class ContractorReleaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorRelease
        fields = ('pk', 'project', 'contractor', '__str__', 'status', 'refund_amount',
                  'refund_account_bank', 'refund_account_number', 'refund_account_depositor',
                  'request_date', 'completion_date', 'note')
